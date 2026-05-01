"""
Gemma-powered section extraction from raw PDF text.

Sends text to local Ollama in chunks, asking Gemma to identify and extract
each numbered section with its title and full content. Returns structured
data matching SectionSchema.

This is the primary extraction method — not a fallback. PDF text from
legislation is too messy (multi-column, footnotes, headers/footers,
amendment annotations) for reliable regex-based parsing.
"""

from __future__ import annotations

import json
import re
import textwrap
import time
from typing import Optional

import requests
from rich.console import Console

from config import CHUNK_OVERLAP, CHUNK_SIZE, DEFAULT_MODEL, GEMINI_CHUNK_SIZE, GROQ_CHUNK_SIZE, OLLAMA_URL

console = Console()

# ── Prompts ─────────────────────────────────────────────────────────

SECTION_EXTRACTION_PROMPT = textwrap.dedent("""\
    You are a legal document parser. You will receive raw text extracted from a {country} legislation PDF.

    Your task: identify every numbered section/clause and extract it as structured JSON.

    For each section output:
    {{
      "sectionNumber": "Section 14" or "14(1)" — use the exact numbering from the text,
      "title": "Short descriptive title for this section",
      "content": "The FULL verbatim legal text of this section — include all subsections, paragraphs, provisos. Do NOT truncate."
    }}

    Rules:
    - Include ALL sections you find, even short ones
    - The "content" field must contain the COMPLETE text — every word, every subsection
    - If a section has subsections like (a), (b), (c) — include them all in content
    - Ignore page headers, footers, page numbers, gazette metadata
    - Ignore the table of contents — only extract actual section text
    - If text is cut off (chunk boundary), extract what you have — it will be merged later
    - Section titles: if the act doesn't have explicit titles, create a brief descriptive one
    - IMPORTANT: If the document contains text in multiple languages, extract ONLY the English text. Discard any Afrikaans, Zulu, Xhosa, Sotho, or other non-English sentences or paragraphs.

    Respond with ONLY a JSON array. No explanation, no markdown fences, no preamble.
    If you find no sections in this chunk, respond with: []

    TEXT:
    {text}
""")

METADATA_EXTRACTION_PROMPT = textwrap.dedent("""\
    You are a legal document parser. Extract metadata from this legislation PDF text.

    Return ONLY a JSON object with these fields:
    {{
      "name": "Full formal name of the act (e.g. 'Insurance Act 18 of 2017')",
      "actNumber": "Official act number (e.g. '18 of 2017', 'No. 51 of 1974'). Use the act number exactly as written.",
      "description": "2-3 sentence plain-language summary of what this act does",
      "effectiveDate": "YYYY-MM-DD if found, otherwise empty string",
      "lastAmended": "YYYY-MM-DD if found, otherwise empty string"
    }}

    No explanation, no markdown fences.

    TEXT (first 3000 chars):
    {text}
""")


class LLMExtractor:
    """Extract structured legal sections from raw PDF text using a local or cloud LLM."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_URL,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        provider: str = "ollama",  # "ollama", "groq", or "gemini"
        api_key: str = "",
    ):
        self.model = model
        self.base_url = base_url
        self.chunk_overlap = chunk_overlap
        self.provider = provider
        self.api_key = api_key
        if provider == "groq":
            self.chunk_size = GROQ_CHUNK_SIZE
        elif provider == "gemini":
            self.chunk_size = GEMINI_CHUNK_SIZE
        else:
            self.chunk_size = chunk_size

    # ── Public API ──────────────────────────────────────────────────

    def extract_sections(self, raw_text: str, country_code: str) -> list[dict]:
        """
        Extract all sections from PDF text.
        Chunks the text and sends each chunk to Gemma, then merges results.
        """
        if not raw_text or len(raw_text.strip()) < 100:
            console.print("  [red]PDF text too short or empty[/red]")
            return []

        chunks = self._chunk_text(raw_text)
        console.print(f"  [dim]Split into {len(chunks)} chunk(s) for LLM processing[/dim]")

        all_sections = []
        for i, chunk in enumerate(chunks):
            console.print(
                f"  [dim]Chunk {i+1}/{len(chunks)} ({len(chunk):,} chars) — "
                f"waiting for {self.provider}...[/dim]",
                end="\r",
            )
            t0 = time.time()
            prompt = SECTION_EXTRACTION_PROMPT.format(
                country=country_code, text=chunk
            )
            result = self._call_llm(prompt)
            elapsed = time.time() - t0
            sections = self._parse_sections_response(result)
            found = len(sections)
            console.print(
                f"  [dim]Chunk {i+1}/{len(chunks)} ({len(chunk):,} chars) — "
                f"{elapsed:.0f}s — [cyan]{found} section(s) found[/cyan][/dim]"
            )
            if sections:
                all_sections.extend(sections)

        # Deduplicate sections that may appear in overlapping chunks
        merged = self._deduplicate_sections(all_sections)
        console.print(f"  [green]Total: {len(merged)} unique section(s)[/green]")
        return merged

    def extract_metadata(self, raw_text: str) -> dict:
        """
        Extract act metadata (name, description, dates) from the first part of the PDF.
        Returns dict with name, description, effectiveDate, lastAmended.
        """
        # Only send the beginning of the doc for metadata
        text_sample = raw_text[:3000]
        prompt = METADATA_EXTRACTION_PROMPT.format(text=text_sample)
        result = self._call_llm(prompt)
        return self._parse_metadata_response(result)

    # ── LLM communication ───────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "groq":
            return self._call_groq(prompt)
        if self.provider == "gemini":
            return self._call_gemini(prompt)
        return self._call_ollama(prompt)

    def _call_gemini(self, prompt: str) -> str:
        """Send prompt to Google Gemini API and return response text."""
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            for attempt in range(4):
                try:
                    resp = client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=8192,
                        ),
                    )
                    return resp.text or ""
                except Exception as e:
                    msg = str(e)
                    if "429" in msg or "quota" in msg.lower() or "503" in msg or "unavailable" in msg.lower():
                        # Parse "Please retry in X.XXs" from the error message
                        m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", msg)
                        wait = float(m.group(1)) + 1 if m else 2 ** attempt * 10
                        wait = min(wait, 120)
                        label = "quota" if "429" in msg else "unavailable (503)"
                        console.print(
                            f"  [yellow]Gemini {label} — waiting {wait:.0f}s "
                            f"(attempt {attempt+1}/3)[/yellow]"
                        )
                        time.sleep(wait)
                    else:
                        console.print(f"  [red]Gemini error: {e}[/red]")
                        return ""
            console.print("  [red]Gemini quota: gave up after 4 attempts[/red]")
            return ""
        except ImportError:
            console.print(
                "  [red]google-genai not installed. Run: pip install google-genai[/red]"
            )
            return ""

    def _call_groq(self, prompt: str) -> str:
        """Send prompt to Groq API and return response text."""
        try:
            from groq import Groq, RateLimitError
            client = Groq(api_key=self.api_key)
            for attempt in range(4):
                try:
                    resp = client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        # Keep total tokens (input ~4.9k + output) under free-tier 12k TPM limit.
                        max_tokens=4096,
                    )
                    return resp.choices[0].message.content or ""
                except RateLimitError as e:
                    wait = 2 ** attempt * 15  # 15s, 30s, 60s, 120s
                    console.print(
                        f"  [yellow]Groq rate limit — waiting {wait}s before retry {attempt+1}/3[/yellow]"
                    )
                    time.sleep(wait)
            console.print("  [red]Groq rate limit: gave up after 4 attempts[/red]")
            return ""
        except Exception as e:
            console.print(f"  [red]Groq error: {e}[/red]")
            return ""

    def _call_ollama(self, prompt: str) -> str:
        """Send prompt to Ollama and return response text."""
        try:
            resp = requests.post(
                self.base_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 16384,  # enough for a full JSON array from an 8K char chunk
                        "top_p": 0.9,
                    },
                },
                timeout=300,  # CPU inference on large models can be slow
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.ConnectionError:
            console.print(
                "  [bold red]Cannot connect to Ollama![/bold red]\n"
                "  Run: ollama serve"
            )
            return ""
        except requests.Timeout:
            console.print("  [red]Ollama request timed out (180s)[/red]")
            return ""
        except Exception as e:
            console.print(f"  [red]Ollama error: {e}[/red]")
            return ""

    # ── Text chunking ───────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks, trying to break at section boundaries.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size

            if end < len(text):
                # Try to break at a section boundary
                # Look for "Section \d+" or numbered headings near the end
                search_zone = text[end - 500 : end + 500] if end + 500 < len(text) else text[end - 500:]
                boundary = re.search(
                    r"\n\s*(?:Section|SECTION|CHAPTER|PART)\s+\d+",
                    search_zone,
                )
                if boundary:
                    # Adjust end to break at the section boundary
                    end = (end - 500) + boundary.start()

            chunk = text[start:end]
            chunks.append(chunk.strip())

            # Move start forward, leaving overlap
            start = end - self.chunk_overlap if end < len(text) else end

        return [c for c in chunks if c]

    # ── Response parsing ────────────────────────────────────────────

    def _parse_sections_response(self, response: str) -> list[dict]:
        """Parse LLM response into list of section dicts."""
        if not response:
            return []

        # Strip markdown fences if present
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        # Find the array boundaries
        arr_start = cleaned.find("[")
        arr_end = cleaned.rfind("]")
        if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
            cleaned = cleaned[arr_start : arr_end + 1]
        elif arr_start != -1:
            # Truncated response — no closing bracket; salvage complete objects
            cleaned = cleaned[arr_start:]

        # Try to parse; on failure apply progressive repair strategies
        sections = None
        try:
            sections = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                repaired = self._repair_json(cleaned)
                sections = json.loads(repaired)
            except json.JSONDecodeError:
                # Last resort: extract individual complete JSON objects
                sections = self._extract_json_objects(cleaned)
                if not sections:
                    console.print(f"    [red]JSON parse error: could not salvage any objects[/red]")
                    return []

        if not isinstance(sections, list):
            if isinstance(sections, dict):
                sections = [sections]
            else:
                return []

        valid = []
        for s in sections:
            if not isinstance(s, dict):
                continue
            if all(k in s for k in ("sectionNumber", "title", "content")):
                sec_num = str(s["sectionNumber"]).strip()
                title = str(s["title"]).strip()
                content = str(s["content"]).strip()
                if content and len(content) >= 10:
                    valid.append({
                        "sectionNumber": sec_num,
                        "title": title,
                        "content": content,
                    })

        return valid

    @staticmethod
    def _repair_json(text: str) -> str:
        """Apply common JSON repair strategies for Ollama output."""
        # Remove control characters that break JSON strings (except \t \n \r)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Fix invalid unicode escapes like \uXXXX that are not valid hex
        text = re.sub(
            r"\\u([0-9a-fA-F]{0,3}[^0-9a-fA-F])",
            lambda m: "\\\\u" + m.group(1),
            text,
        )
        # Remove trailing commas before ] or }
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return text

    @staticmethod
    def _extract_json_objects(text: str) -> list[dict]:
        """
        Salvage complete JSON objects from a truncated/broken array string.
        Walks the text char-by-char tracking brace depth to find complete {...} objects.
        """
        objects = []
        depth = 0
        start = None
        in_string = False
        escape_next = False

        for i, ch in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            objects.append(obj)
                    except json.JSONDecodeError:
                        try:
                            obj = json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
                            if isinstance(obj, dict):
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                    start = None

        return objects

    def _parse_metadata_response(self, response: str) -> dict:
        """Parse metadata extraction response."""
        defaults = {"name": "", "actNumber": "", "description": "", "effectiveDate": "", "lastAmended": ""}
        if not response:
            return defaults

        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        # Find JSON object
        obj_start = cleaned.find("{")
        obj_end = cleaned.rfind("}")
        if obj_start != -1 and obj_end != -1:
            cleaned = cleaned[obj_start : obj_end + 1]

        try:
            data = json.loads(self._repair_json(cleaned))
            if isinstance(data, dict):
                return {
                    "name": str(data.get("name", "")),
                    "actNumber": str(data.get("actNumber", "")),
                    "description": str(data.get("description", "")),
                    "effectiveDate": str(data.get("effectiveDate", "")),
                    "lastAmended": str(data.get("lastAmended", "")),
                }
        except json.JSONDecodeError:
            pass

        return defaults

    # ── Deduplication ───────────────────────────────────────────────

    def _deduplicate_sections(self, sections: list[dict]) -> list[dict]:
        """
        Remove duplicate sections from overlapping chunks.
        Keeps the version with the longest content.
        """
        by_number: dict[str, dict] = {}
        for s in sections:
            key = self._normalize_section_key(s["sectionNumber"])
            existing = by_number.get(key)
            if not existing or len(s["content"]) > len(existing["content"]):
                by_number[key] = s

        # Return in order of section number
        result = list(by_number.values())
        result.sort(key=lambda s: self._section_sort_key(s["sectionNumber"]))
        return result

    @staticmethod
    def _normalize_section_key(sec_num: str) -> str:
        """Normalize section number for dedup comparison."""
        # Extract just the numbers: "Section 14(1)" → "14(1)"
        m = re.search(r"(\d+(?:[A-Za-z])?(?:\(\d+\))?)", sec_num)
        return m.group(1) if m else sec_num.lower().strip()

    @staticmethod
    def _section_sort_key(sec_num: str) -> tuple:
        """Sort key for section numbers: Section 2 < Section 10 < Section 10A."""
        m = re.search(r"(\d+)([A-Za-z])?", sec_num)
        if m:
            num = int(m.group(1))
            suffix = m.group(2) or ""
            return (num, suffix)
        return (9999, sec_num)
