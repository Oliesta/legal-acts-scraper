"""
United States scraper.

US federal legislation PDFs from GPO (govinfo.gov), congress.gov, etc.
Cleans up GPO boilerplate, public law headers, and USC references.
"""

from __future__ import annotations

import re
from pathlib import Path

from base_scraper import BaseScraper


class USScraper(BaseScraper):
    country_code = "US"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with US-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_us_text(raw)

    @staticmethod
    def _clean_us_text(text: str) -> str:
        """Remove US federal legislation PDF artifacts."""
        # GPO header/footer
        text = re.sub(r"(?mi)^.*VerDate.*$", "", text)
        text = re.sub(r"(?mi)^.*Jkt\s+\d+.*$", "", text)
        text = re.sub(r"(?mi)^.*PO\s+\d+.*$", "", text)
        text = re.sub(r"(?mi)^.*Sfmt\s+\d+.*$", "", text)
        text = re.sub(r"(?mi)^.*Frm\s+\d+.*$", "", text)

        # Congressional Record line numbers
        text = re.sub(r"(?m)^\s*\d{1,4}\s{2,}", "", text)

        # Statutes at Large page references
        text = re.sub(r"(?mi)^.*STAT\.\s*\d+.*$", "", text)

        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()