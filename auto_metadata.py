"""auto_metadata.py

Download/extract text from a PDF (URL or local path), call the Gemma LLM via config.OLLAMA_URL to generate missing act metadata, and optionally append the generated act entry to the appropriate COUNTRY _ACTS list inside config.py.

Usage (examples):
    # generate metadata and print
    python auto_metadata.py --pdf https://example.org/act.pdf --country ZA

    # generate metadata and append to config.py in-place
    python auto_metadata.py --pdf ./pdfs/za/act.pdf --country ZA --write

Notes:
  - Requires: requests, pdfminer.six (or PyPDF2 as fallback). Install with: pip install requests pdfminer.six PyPDF2
  - The script will create a backup of config.py as config.py.bak before modifying it.
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Dict, Optional

import requests

# Try to import pdfminer; fall back to PyPDF2
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    _HAS_PDFMINER = True
except Exception:
    _HAS_PDFMINER = False
    try:
        import PyPDF2
        _HAS_PYPDF2 = True
    except Exception:
        _HAS_PYPDF2 = False

# import config values
import config

PDF_CACHE_DIR = getattr(config, "PDF_CACHE_DIR", "pdf_cache")
os.makedirs(PDF_CACHE_DIR, exist_ok=True)

def download_pdf(url: str) -> str:
    """Download PDF to PDF_CACHE_DIR and return local path."""
    local_filename = os.path.join(PDF_CACHE_DIR, os.path.basename(url.split("?")[0]))
    if os.path.exists(local_filename):
        return local_filename
    headers = {"User-Agent": getattr(config, "USER_AGENT", "legal-acts-scraper")}
    timeout = getattr(config, "REQUEST_TIMEOUT", 60)
    retries = getattr(config, "MAX_RETRIES", 3)
    delay = getattr(config, "REQUEST_DELAY", 2.0)
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            with open(local_filename, "wb") as f:
                f.write(r.content)
            return local_filename
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(delay)
    return local_filename

def extract_text_from_pdf(path: str) -> str:
    """Extract text from a PDF file using pdfminer or PyPDF2 fallback."""
    if _HAS_PDFMINER:
        try:
            return pdfminer_extract_text(path)
        except Exception:
            pass
    if _HAS_PYPDF2:
        try:
            with open(path, "rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                pages = []
                for p in reader.pages:
                    try:
                        pages.append(p.extract_text() or "")
                    except Exception:
                        pages.append("")
                return "\n\n".join(pages)
        except Exception:
            pass
    raise RuntimeError("No PDF text extraction available: install pdfminer.six or PyPDF2")

def chunk_text(text: str, chunk_size: int, overlap: int):
    """Yield overlapping chunks of text (character-based)."""
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        yield text[start:end]
        if end == length:
            break
        start = max(0, end - overlap)

def call_llm(prompt: str, max_tokens: int = 1024) -> str:
    """Call the Gemma/OLLAMA endpoint defined in config.py and return text response.

    The script sends a JSON body which many Ollama-style local servers accept. If your Ollama
    install requires a different shape, adapt this function accordingly.
    """
    url = getattr(config, "OLLAMA_URL", None)
    if not url:
        raise RuntimeError("OLLAMA_URL not set in config.py")
    model = getattr(config, "DEFAULT_MODEL", None)
    payload = {
        # Ollama may accept different parameter names depending on version. This is a reasonable
        # default for many local LLM APIs; adjust if your server expects a different schema.
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    # Attempt to parse common response shapes
    try:
        j = resp.json()
        # If the response has a top-level 'text' or 'response' field, prefer that
        for key in ("text", "response", "content", "output"):
            if key in j and isinstance(j[key], str):
                return j[key]
        # Some Ollama variants return {'choices': [{'message': {'content': '...'}}]}
        if "choices" in j and isinstance(j["choices"], list) and len(j["choices"]) > 0:
            first = j["choices"][0]
            if isinstance(first, dict):
                # Try common nested keys
                for path in [("message", "content"), ("text",), ("content",)]:
                    cursor = first
                    for p in path:
                        if isinstance(cursor, dict) and p in cursor:
                            cursor = cursor[p]
                        else:
                            cursor = None
                            break
                    if isinstance(cursor, str):
                        return cursor
        # As a last resort, return stringified JSON
        return json.dumps(j)
    except ValueError:
        # Not JSON — return raw text
        return resp.text

def parse_llm_json_response(text: str) -> Dict:
    """Try to extract JSON object from LLM text.

    The LLM is prompted to return a single JSON object; we robustly search for the first
    JSON object inside the text and parse it.
    """
    # Find the first '{' and last '}' that form a valid JSON object
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")
    # naive approach: try incrementally larger substrings until json.loads succeeds
    for end in range(len(text), start, -1):
        try:
            candidate = text[start:end]
            obj = json.loads(candidate)
            return obj
        except Exception:
            continue
    # fallback: try to extract with regex capturing {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception as e:
            raise ValueError("Failed to parse JSON from LLM response") from e
    raise ValueError("Failed to parse JSON from LLM response")

def build_prompt_for_metadata(text: str) -> str:
    """Construct a prompt instructing the LLM to extract metadata as JSON."""
    instructions = (
        "You are an assistant that extracts structured metadata from a South African/other legal act PDF.\n"
        "Return a single JSON object ONLY, with these keys: short_name, act_number, category, effective_date, description, last_amended.\n"
        "- short_name: short abbreviation (2-6 chars ideally), if not obvious set empty string.\n"
        "- act_number: the official act number/title, if available.\n"
        "- category: one-word category such as 'consumer', 'insurance', 'tax', 'criminal', 'labour', 'health', or leave empty.\n"
        "- effective_date: YYYY-MM-DD format if you can find an effective date, otherwise empty string.\n"
        "- description: 1-2 sentence summary of the act's purpose or scope.\n"
        "- last_amended: YYYY-MM-DD or year if available, else empty string.\n"
        "If you cannot find a field, set it to an empty string. Do not output any explanation, only the JSON object.\n\n"
        "Text:\n\n"
    )
    # Add a limited amount of text to stay within token/context constraints
    max_chars = getattr(config, "CHUNK_SIZE", 6000)
    snippet = text[: max_chars * 3]  # give the LLM more context if available but cap
    return instructions + snippet

def generate_metadata_from_pdf(path_or_url: str) -> Dict:
    """Main function: download/extract text, call LLM, parse JSON result."""
    if re.match(r"^https?://", path_or_url, re.I):
        local_path = download_pdf(path_or_url)
    else:
        local_path = path_or_url
    text = extract_text_from_pdf(local_path)
    prompt = build_prompt_for_metadata(text)
    llm_text = call_llm(prompt)
    metadata = parse_llm_json_response(llm_text)
    # Ensure keys exist
    for k in ("short_name", "act_number", "category", "effective_date", "description", "last_amended"):
        metadata.setdefault(k, "")
    # Add source/path information
    entry = {
        "source": "url" if re.match(r"^https?://", path_or_url, re.I) else "file",
    }
    if entry["source"] == "url":
        entry["url"] = path_or_url
    else:
        entry["path"] = path_or_url
    entry.update(metadata)
    return entry

def _serialize_entry(entry: Dict) -> str:
    """Return a pretty-printed Python dict literal for insertion into config.py."""
    # Minimal deterministic ordering
    keys = [
        "source",
        "url",
        "path",
        "short_name",
        "act_number",
        "category",
        "effective_date",
        "last_amended",
        "description",
    ]
    parts = []
    parts.append("{\n")
    first = True
    for k in keys:
        if k in entry and entry[k] not in (None, ""):
            if not first:
                parts.append(",\n")
            v = entry[k]
            # ensure string quoting and escaping
            parts.append(f"    \"{k}\": \"{str(v).replace('\\', '\\\\').replace('\"', '\\"')}\"")
            first = False
    parts.append("}\n")
    # join with newlines and proper indentation
    body = "".join(parts)
    return body

def append_entry_to_config_py(entry: Dict, country_code: str = "ZA", config_path: str = "config.py") -> None:
    """Append an entry to the <CC>_ACTS list inside config.py in-place.

    Creates a backup config.py.bak before writing. This function uses a simple bracket
    depth scanner and is somewhat brittle; inspect the resulting file after running.
    """
    var_name = f"{country_code}_ACTS"
    with open(config_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    idx = src.find(f"{var_name} = [")
    if idx == -1:
        raise ValueError(f"Could not find variable {var_name} in {config_path}")
    # Find the opening bracket position
    open_idx = src.find("[", idx)
    # Walk forward to find the matching closing bracket
    depth = 0
    insert_pos = None
    for i in range(open_idx, len(src)):
        c = src[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                insert_pos = i
                break
    if insert_pos is None:
        raise ValueError("Could not determine end of list in config.py")
    # Build entry string with indentation matching typical file
    entry_py = _serialize_entry(entry)
    insertion = "\n    " + entry_py.replace("\n", "\n    ") + ",\n"
    new_src = src[:insert_pos] + insertion + src[insert_pos:]
    # Backup
    bak = config_path + ".bak"
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(src)
    with open(config_path, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    print(f"Appended entry to {var_name} in {config_path} (backup at {bak})")

def main(argv=None):
    p = argparse.ArgumentParser(description="Generate act metadata from a PDF and optionally save to config.py")
    p.add_argument("--pdf", required=True, help="URL or local path to PDF")
    p.add_argument("--country", required=True, help="Country code (e.g. ZA, GB, US, IN, AU)")
    p.add_argument("--write", action="store_true", help="Write the generated entry into config.py")
    args = p.parse_args(argv)

    entry = generate_metadata_from_pdf(args.pdf)
    print("Generated entry:")
    print(json.dumps(entry, indent=2, ensure_ascii=False))

    if args.write:
        cfg_path = os.path.join(os.path.dirname(__file__), "config.py")
        append_entry_to_config_py(entry, country_code=args.country.upper(), config_path=cfg_path)


if __name__ == "__main__":
    main()