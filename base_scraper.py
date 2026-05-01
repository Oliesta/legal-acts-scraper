"""
Base scraper: PDF download, text extraction, LLM orchestration.

Handles:
  - Downloading PDFs from URLs (with caching)
  - Extracting text via pdftotext / pdfplumber / pypdf / OCR fallback
  - Coordinating with LLM extractor for section parsing
  - Schema validation and JSON output
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from pydantic import ValidationError
from rich.console import Console

from config import (
    MAX_RETRIES,
    OUTPUT_DIR,
    PDF_CACHE_DIR,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from llm_extractor import LLMExtractor
from schema import ActSchema, SectionSchema

console = Console()

# Maps act category → ContraSnap document types for applicableDocumentTypes.
# "consumer" acts use the catch-all list so gym/phone/lease/other contracts
# all get grounded against the CPA/CRA/ACL etc.
_CATEGORY_TO_DOC_TYPES: dict[str, list[str]] = {
    "employment": ["employment"],
    "insurance":  ["insurance"],
    "consumer":   ["gym", "phone", "lease", "other"],
    "rental":     ["lease"],
    "credit":     ["other"],
    "general":    [],  # universal — included for every document type
}


def _subprocess_kwargs() -> dict:
    """
    Return platform-specific kwargs for subprocess.run.
    On Windows: suppress the console window that would otherwise flash.
    """
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}


class BaseScraper:
    """Base class for all country scrapers."""

    country_code: str = ""

    def __init__(self, act_configs: list[dict], llm: LLMExtractor):
        self.act_configs = act_configs
        self.llm = llm
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,*/*",
        })
        self.results: list[dict] = []
        self.errors: list[str] = []

    # ── PDF acquisition ────────────────────────────────────────────────

    def get_pdf_path(self, config: dict) -> Optional[Path]:
        """Get path to PDF — download if URL source, validate if file source."""
        source = config.get("source", "url")

        if source == "file":
            path = Path(config["path"])
            if not path.exists():
                self.errors.append(f"{config['short_name']}: File not found: {path}")
                return None
            return path

        elif source == "url":
            return self._download_pdf(config)

        else:
            self.errors.append(f"{config['short_name']}: Unknown source type: {source}")
            return None

    def _download_pdf(self, config: dict) -> Optional[Path]:
        """Download a PDF from URL, cache locally."""
        os.makedirs(PDF_CACHE_DIR, exist_ok=True)

        cache_path = Path(PDF_CACHE_DIR) / f"{self.country_code}_{config['short_name']}.pdf"
        if cache_path.exists():
            with open(cache_path, "rb") as f:
                header = f.read(4)
            if header == b"%PDF":
                console.print(f"  [dim]Using cached PDF: {cache_path}[/dim]")
                return cache_path
            console.print(f"  [yellow]Cached file is not a PDF — re-downloading[/yellow]")
            cache_path.unlink()

        url = config["url"]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                console.print(f"  [dim]Downloading PDF (attempt {attempt})...[/dim]")
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
                resp.raise_for_status()

                if resp.status_code == 202:
                    for poll in range(8):
                        wait = 15 + poll * 10
                        console.print(
                            f"  [dim]Server generating PDF (202) — "
                            f"waiting {wait}s (poll {poll+1}/8)...[/dim]"
                        )
                        time.sleep(wait)
                        resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
                        resp.raise_for_status()
                        if resp.status_code == 200:
                            break
                    else:
                        self.errors.append(
                            f"{config['short_name']}: PDF generation timed out after polling"
                        )
                        return None

                with open(cache_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                with open(cache_path, "rb") as f:
                    header = f.read(4)
                if header != b"%PDF":
                    try:
                        with open(cache_path, encoding="utf-8", errors="replace") as fh:
                            html_content = fh.read(200000)
                    except Exception:
                        html_content = ""
                    cache_path.unlink()

                    m = re.search(
                        r'(/[A-Z][A-Z0-9]*/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}/text/original/pdf[^"<\s]*)',
                        html_content,
                    )
                    if m:
                        from urllib.parse import urljoin
                        direct_url = urljoin(url, m.group(1))
                        console.print(
                            f"  [dim]Discovered PDF URL from downloads page → {direct_url}[/dim]"
                        )
                        try:
                            resp2 = self.session.get(
                                direct_url, timeout=REQUEST_TIMEOUT, stream=True
                            )
                            resp2.raise_for_status()
                            with open(cache_path, "wb") as fh:
                                for chunk in resp2.iter_content(chunk_size=8192):
                                    fh.write(chunk)
                            with open(cache_path, "rb") as fh:
                                header2 = fh.read(4)
                            if header2 == b"%PDF":
                                size_mb = cache_path.stat().st_size / (1024 * 1024)
                                console.print(
                                    f"  [green]Downloaded {size_mb:.1f} MB → {cache_path}[/green]"
                                )
                                return cache_path
                            if cache_path.exists():
                                cache_path.unlink()
                        except Exception as disc_err:
                            console.print(
                                f"  [red]Auto-discovered URL failed: {disc_err}[/red]"
                            )
                            if cache_path.exists():
                                cache_path.unlink()

                    content_type = resp.headers.get("Content-Type", "")
                    self.errors.append(
                        f"{config['short_name']}: URL did not return a PDF "
                        f"(Content-Type: {content_type}, got: {header!r})"
                    )
                    return None

                size_mb = cache_path.stat().st_size / (1024 * 1024)
                console.print(f"  [green]Downloaded {size_mb:.1f} MB → {cache_path}[/green]")
                return cache_path

            except requests.RequestException as e:
                console.print(f"  [red]Download error: {e}[/red]")
                if attempt < MAX_RETRIES:
                    time.sleep(REQUEST_DELAY * attempt)

        self.errors.append(f"{config['short_name']}: Failed to download after {MAX_RETRIES} attempts")
        return None

    # ── Text extraction ───────────────────────────────────────────────

    def extract_text(self, pdf_path: Path) -> str:
        text = self._extract_with_pdftotext(pdf_path)
        if text and len(text.strip()) > 200:
            return text

        console.print("  [yellow]pdftotext returned little text, trying pdfplumber...[/yellow]")
        text = self._extract_with_pdfplumber(pdf_path)
        if text and len(text.strip()) > 200:
            return text

        console.print("  [yellow]pdfplumber returned little text, trying pypdf...[/yellow]")
        text = self._extract_with_pypdf(pdf_path)
        if text and len(text.strip()) > 200:
            return text

        console.print("  [yellow]pypdf returned little text, trying OCR...[/yellow]")
        text = self._extract_with_ocr(pdf_path)
        if text and len(text.strip()) > 200:
            return text

        console.print("  [red]All text extraction methods returned minimal text[/red]")
        return text or ""

    def _extract_with_pdftotext(self, pdf_path: Path) -> str:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                **_subprocess_kwargs(),
            )
            if result.returncode == 0:
                return self._clean_pdf_text(result.stdout)
        except FileNotFoundError:
            console.print(
                "  [dim]pdftotext not found — install poppler "
                "(Linux: apt install poppler-utils | macOS: brew install poppler)[/dim]"
            )
        except subprocess.TimeoutExpired:
            console.print("  [red]pdftotext timed out[/red]")
        return ""

    def _extract_with_pdfplumber(self, pdf_path: Path) -> str:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(str(pdf_path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        pages.append(f"--- PAGE {i + 1} ---\n{text}")
            return self._clean_pdf_text("\n\n".join(pages))
        except ImportError:
            console.print("  [dim]pdfplumber not installed (pip install pdfplumber)[/dim]")
            return ""
        except Exception as e:
            console.print(f"  [red]pdfplumber error: {e}[/red]")
            return ""

    def _extract_with_pypdf(self, pdf_path: Path) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"--- PAGE {i+1} ---\n{text}")
            return self._clean_pdf_text("\n\n".join(pages))
        except Exception as e:
            console.print(f"  [red]pypdf error: {e}[/red]")
            return ""

    def _extract_with_ocr(self, pdf_path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image

            if sys.platform == "win32":
                import shutil
                if not shutil.which("tesseract"):
                    default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                    if os.path.exists(default_path):
                        pytesseract.pytesseract.tesseract_cmd = default_path
                    else:
                        console.print("  [dim]Tesseract not found[/dim]")
                        return ""

            img_dir = Path(PDF_CACHE_DIR) / "ocr_temp"
            img_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                ["pdftoppm", "-jpeg", "-r", "200", str(pdf_path), str(img_dir / "page")],
                capture_output=True,
                timeout=120,
                **_subprocess_kwargs(),
            )
            if result.returncode != 0:
                return ""

            pages = []
            for img_file in sorted(img_dir.glob("page-*.jpg")):
                img = Image.open(img_file)
                text = pytesseract.image_to_string(img)
                if text.strip():
                    pages.append(text)
                img_file.unlink()

            return self._clean_pdf_text("\n\n".join(pages))
        except ImportError:
            console.print("  [dim]pytesseract/Pillow not installed[/dim]")
            return ""
        except Exception as e:
            console.print(f"  [red]OCR error: {e}[/red]")
            return ""

    @staticmethod
    def _clean_pdf_text(text: str) -> str:
        text = text.replace("\f", "\n\n")
        text = re.sub(r"\xa0", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r"(?m)^.{0,5}(?:Government Gazette|Staatskoerant).*$", "", text)
        text = re.sub(r"‘{2}", '"', text)
        text = re.sub(r"’{2}", '"', text)
        text = text.replace("‘", "'").replace("’", "'")
        return text.strip()

    # ── Act building ─────────────────────────────────────────────────

    def build_act(
        self,
        config: dict,
        name: str,
        sections: list[dict],
        description: str = "",
    ) -> Optional[ActSchema]:
        desc = description or config.get("description", "")
        if not desc or len(desc) < 10:
            desc = f"{name} — legislation from {self.country_code}."

        effective_date = config.get("effective_date", "")
        if not effective_date or not re.match(r"\d{4}-\d{2}-\d{2}", effective_date):
            effective_date = "2000-01-01"

        act_number = config.get("act_number") or config.get("short_name", "unknown")

        try:
            act = ActSchema(
                name=name,
                shortName=config["short_name"],
                actNumber=act_number,
                country=self.country_code,
                category=config["category"],
                effectiveDate=effective_date,
                lastAmended=config.get("last_amended", ""),
                description=desc,
                sections=[SectionSchema(**s) for s in sections],
            )
            # Stamp applicableDocumentTypes using the ContraSnap-aware mapping.
            # "consumer" → ["gym","phone","lease","other"] so CPA/CRA sections
            # reach all consumer contract types, not just those labelled "consumer".
            doc_types = _CATEGORY_TO_DOC_TYPES.get(act.category, [act.category])
            for section in act.sections:
                if not section.applicableDocumentTypes:
                    section.applicableDocumentTypes = doc_types
            return act
        except ValidationError as e:
            self.errors.append(
                f"Validation error for {config['short_name']}: "
                f"{e.errors()[0]['msg'] if e.errors() else 'unknown'}"
            )
            return None

    def _fetch_html_text(self, config: dict) -> str:
        url = config["url"]
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer",
                              "aside", "noscript", "form", "button"]):
                tag.decompose()
            return self._clean_pdf_text(soup.get_text(separator="\n", strip=True))
        except Exception as e:
            self.errors.append(f"{config['short_name']}: HTML fetch error: {e}")
            return ""

    # ── Main pipeline ───────────────────────────────────────────────

    def process_act(self, config: dict) -> Optional[ActSchema]:
        """
        Full pipeline for a single act:
        1. Get text (PDF download/local, or HTML fetch)
        2. LLM extracts sections
        2b. Filter to target_sections if specified in config
        3. LLM extracts metadata (if not provided)
        4. Validate and return
        """
        # Step 1: Get text
        source = config.get("source", "url")
        if source == "html":
            console.print(f"  Fetching HTML text from {config['url'].split('/')[-2]}...")
            raw_text = self._fetch_html_text(config)
        else:
            pdf_path = self.get_pdf_path(config)
            if not pdf_path:
                return None
            console.print(f"  Extracting text from {pdf_path.name}...")
            raw_text = self.extract_text(pdf_path)

        if not raw_text or len(raw_text) < 200:
            self.errors.append(f"{config['short_name']}: Could not extract meaningful text")
            return None
        console.print(f"  [dim]Extracted {len(raw_text):,} characters[/dim]")

        # Step 2: LLM extracts sections
        console.print(f"  Sending to {self.llm.model} for section extraction...")
        sections = self.llm.extract_sections(raw_text, self.country_code)
        if not sections:
            self.errors.append(f"{config['short_name']}: LLM found no sections in PDF text")
            return None

        # Step 2b: Filter to target_sections if specified.
        # Acts like LRA have 200+ sections; we only want the rights-granting
        # ones (e.g. 185-188) not definitions and procedural provisions.
        target_sections = config.get("target_sections")
        if target_sections:
            target_keys = set()
            for t in target_sections:
                m = re.search(r"(\d+)", str(t))
                if m:
                    target_keys.add(m.group(1))
            filtered = [
                s for s in sections
                if (m := re.search(r"(\d+)", s["sectionNumber"])) and m.group(1) in target_keys
            ]
            console.print(
                f"  [dim]target_sections filter: kept {len(filtered)}/{len(sections)} "
                f"(targets: {', '.join(sorted(target_keys, key=lambda x: int(x)))})[/dim]"
            )
            if not filtered:
                self.errors.append(
                    f"{config['short_name']}: target_sections filter matched nothing — "
                    f"verify the section numbers exist in the PDF"
                )
                return None
            sections = filtered

        # Step 3: Extract metadata if needed
        name = config.get("name", "")
        description = config.get("description", "")
        needs_meta = not name or not description or not config.get("act_number") or not config.get("effective_date")
        if needs_meta:
            console.print("  [dim]Extracting metadata from PDF...[/dim]")
            meta = self.llm.extract_metadata(raw_text)
            if not name:
                name = meta.get("name") or ""
            if not config.get("act_number") and meta.get("actNumber"):
                config["act_number"] = meta["actNumber"]
            if not description:
                description = meta.get("description", "")
            if not config.get("effective_date") and meta.get("effectiveDate"):
                config["effective_date"] = meta["effectiveDate"]
        if not name:
            name = f"{config['short_name']} {config.get('act_number', '')}".strip()

        # Step 4: Build and validate
        return self.build_act(config, name, sections, description)

    def run(self) -> list[dict]:
        if not self.act_configs:
            console.print(f"[yellow]No acts configured for {self.country_code}[/yellow]")
            return []

        existing_path = Path(OUTPUT_DIR) / f"{self.country_code}_acts.json"
        done: dict[str, dict] = {}
        if existing_path.exists():
            try:
                with open(existing_path, encoding="utf-8") as f:
                    for entry in json.load(f):
                        done[entry["shortName"]] = entry
                if done:
                    console.print(
                        f"  [dim]Resuming — {len(done)} act(s) already in "
                        f"{existing_path.name}, skipping them[/dim]"
                    )
                self.results = list(done.values())
            except Exception:
                pass

        console.print(f"\n[bold blue]═══ {self.country_code} ═══[/bold blue] {len(self.act_configs)} act(s)\n")

        for i, config in enumerate(self.act_configs):
            short = config["short_name"]
            console.print(f"[bold]({i+1}/{len(self.act_configs)}) {short}[/bold]")

            if short in done:
                console.print(
                    f"  [dim]Already done ({len(done[short].get('sections', []))} sections) — skipping[/dim]\n"
                )
                continue

            act = self.process_act(config)
            if act:
                self.results.append(act.model_dump())
                self.save()
                console.print(
                    f"  [bold green]✓ {act.shortName}[/bold green] — "
                    f"{len(act.sections)} section(s)\n"
                )
            else:
                console.print(f"  [bold red]✗ Failed: {short}[/bold red]\n")

            if i < len(self.act_configs) - 1:
                time.sleep(REQUEST_DELAY)

        console.print(
            f"[bold]{self.country_code} complete:[/bold] "
            f"{len(self.results)} extracted, {len(self.errors)} error(s)"
        )
        return self.results

    def save(self, filename: str | None = None) -> Path:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        fname = filename or f"{self.country_code}_acts.json"
        path = Path(OUTPUT_DIR) / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Saved {len(self.results)} acts → {path}[/green]")
        return path
