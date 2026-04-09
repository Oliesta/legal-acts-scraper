"""
Base scraper: PDF download, text extraction, LLM orchestration.

Handles:
  - Downloading PDFs from URLs (with caching)
  - Extracting text via pdftotext / pypdf / OCR fallback
  - Coordinating with LLM extractor for section parsing
  - Schema validation and JSON output
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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

    # ── PDF acquisition ─────────────────────────────────────────────

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

        # Cache filename based on short_name
        cache_path = Path(PDF_CACHE_DIR) / f"{config['short_name']}.pdf"
        if cache_path.exists():
            console.print(f"  [dim]Using cached PDF: {cache_path}[/dim]")
            return cache_path

        url = config["url"]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                console.print(f"  [dim]Downloading PDF (attempt {attempt})...[/dim]")
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
                resp.raise_for_status()

                # Verify it's actually a PDF
                content_type = resp.headers.get("Content-Type", "")
                if "pdf" not in content_type and not url.endswith(".pdf"):
                    # Check first bytes
                    first_bytes = next(resp.iter_content(chunk_size=8))
                    if not first_bytes.startswith(b"%PDF"):
                        self.errors.append(
                            f"{config['short_name']}: URL did not return a PDF "
                            f"(Content-Type: {content_type})"
                        )
                        return None

                with open(cache_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                size_mb = cache_path.stat().st_size / (1024 * 1024)
                console.print(f"  [green]Downloaded {size_mb:.1f} MB → {cache_path}[/green]")
                return cache_path

            except requests.RequestException as e:
                console.print(f"  [red]Download error: {e}[/red]")
                if attempt < MAX_RETRIES:
                    time.sleep(REQUEST_DELAY * attempt)

        self.errors.append(f"{config['short_name']}: Failed to download after {MAX_RETRIES} attempts")
        return None

    # ── Text extraction ─────────────────────────────────────────────

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF. Tries methods in order:
        1. pdftotext (layout mode — best for legislation)
        2. pypdf (fallback)
        3. OCR via pytesseract (for scanned PDFs)
        """
        text = self._extract_with_pdftotext(pdf_path)
        if text and len(text.strip()) > 200:
            return text

        console.print("  [yellow]pdftotext returned little text, trying pypdf...[/yellow]")
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
        """Extract using pdftotext (poppler) in layout mode."""
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return self._clean_pdf_text(result.stdout)
        except FileNotFoundError:
            console.print("  [dim]pdftotext not found, install poppler-utils[/dim]")
        except subprocess.TimeoutExpired:
            console.print("  [red]pdftotext timed out[/red]")
        return ""

    def _extract_with_pypdf(self, pdf_path: Path) -> str:
        """Extract using pypdf."""
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
        """Extract from scanned PDF using OCR (pdftoppm + pytesseract)."""
        try:
            import pytesseract
            from PIL import Image

            # Convert PDF pages to images
            img_dir = Path(PDF_CACHE_DIR) / "ocr_temp"
            img_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [
                    "pdftoppm", "-jpeg", "-r", "200",
                    str(pdf_path), str(img_dir / "page"),
                ],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                return ""

            # OCR each page image
            pages = []
            for img_file in sorted(img_dir.glob("page-*.jpg")):
                img = Image.open(img_file)
                text = pytesseract.image_to_string(img)
                if text.strip():
                    pages.append(text)
                img_file.unlink()  # cleanup

            return self._clean_pdf_text("\n\n".join(pages))

        except ImportError:
            console.print("  [dim]pytesseract/Pillow not installed for OCR[/dim]")
            return ""
        except Exception as e:
            console.print(f"  [red]OCR error: {e}[/red]")
            return ""

    @staticmethod
    def _clean_pdf_text(text: str) -> str:
        """Clean up raw PDF-extracted text."""
        # Remove form feed characters
        text = text.replace("\f", "\n\n")
        # Normalize whitespace
        text = re.sub(r"\xa0", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Remove common PDF artifacts
        text = re.sub(r"(?m)^.{0,5}(?:Government Gazette|Staatskoerant).*$", "", text)
        return text.strip()

    # ── Act building ────────────────────────────────────────────────

    def build_act(
        self,
        config: dict,
        name: str,
        sections: list[dict],
        description: str = "",
    ) -> Optional[ActSchema]:
        """Validate and build ActSchema from extracted data."""
        desc = description or config.get("description", "")
        if not desc or len(desc) < 10:
            desc = f"{name} — legislation from {self.country_code}."

        effective_date = config.get("effective_date", "")
        if not effective_date or not re.match(r"\d{4}-\d{2}-\d{2}", effective_date):
            effective_date = "2000-01-01"  # placeholder — user should fix

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
            return act
        except ValidationError as e:
            self.errors.append(
                f"Validation error for {config['short_name']}: "
                f"{e.errors()[0]['msg'] if e.errors() else 'unknown'}"
            )
            return None

    # ── Main pipeline ───────────────────────────────────────────────

    def process_act(self, config: dict) -> Optional[ActSchema]:
        """
        Full pipeline for a single act:
        1. Get PDF (download or local)
        2. Extract text
        3. LLM extracts sections
        4. LLM extracts metadata (if not provided)
        5. Validate and return
        """
        # Step 1: Get PDF
        pdf_path = self.get_pdf_path(config)
        if not pdf_path:
            return None

        # Step 2: Extract text
        console.print(f"  Extracting text from {pdf_path.name}...")
        raw_text = self.extract_text(pdf_path)
        if not raw_text or len(raw_text) < 200:
            self.errors.append(f"{config['short_name']}: Could not extract meaningful text from PDF")
            return None
        console.print(f"  [dim]Extracted {len(raw_text):,} characters[/dim]")

        # Step 3: LLM extracts sections
        console.print(f"  Sending to {self.llm.model} for section extraction...")
        sections = self.llm.extract_sections(raw_text, self.country_code)
        if not sections:
            self.errors.append(f"{config['short_name']}: LLM found no sections in PDF text")
            return None

        # Step 4: Extract metadata if needed
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

        # Step 5: Build and validate
        return self.build_act(config, name, sections, description)

    def run(self) -> list[dict]:
        """Scrape all configured acts."""
        if not self.act_configs:
            console.print(f"[yellow]No acts configured for {self.country_code}[/yellow]")
            return []

        console.print(f"\n[bold blue]═══ {self.country_code} ═══[/bold blue] {len(self.act_configs)} act(s)\n")

        for i, config in enumerate(self.act_configs):
            console.print(f"[bold]({i+1}/{len(self.act_configs)}) {config['short_name']}[/bold]")

            act = self.process_act(config)
            if act:
                self.results.append(act.model_dump())
                console.print(
                    f"  [bold green]✓ {act.shortName}[/bold green] — "
                    f"{len(act.sections)} section(s)\n"
                )
            else:
                console.print(f"  [bold red]✗ Failed: {config['short_name']}[/bold red]\n")

            if i < len(self.act_configs) - 1:
                time.sleep(REQUEST_DELAY)

        console.print(
            f"[bold]{self.country_code} complete:[/bold] "
            f"{len(self.results)} extracted, {len(self.errors)} error(s)"
        )
        return self.results

    def save(self, filename: str | None = None) -> Path:
        """Write results to JSON file."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        fname = filename or f"{self.country_code}_acts.json"
        path = Path(OUTPUT_DIR) / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Saved {len(self.results)} acts → {path}[/green]")
        return path