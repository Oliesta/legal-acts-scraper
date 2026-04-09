"""
United Kingdom scraper.

UK legislation PDFs from legislation.gov.uk and related sources.
Cleans up Crown copyright notices, Royal Assent text, and
standard formatting artifacts.
"""

from __future__ import annotations

import re
from pathlib import Path

from base_scraper import BaseScraper


class GBScraper(BaseScraper):
    country_code = "GB"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with UK-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_gb_text(raw)

    @staticmethod
    def _clean_gb_text(text: str) -> str:
        """Remove UK legislation PDF artifacts."""
        # Crown copyright notice
        text = re.sub(r"(?mi)^.*Crown copyright.*$", "", text)
        text = re.sub(r"(?mi)^.*Queen's Printer.*$", "", text)
        text = re.sub(r"(?mi)^.*King's Printer.*$", "", text)

        # Status header bars from legislation.gov.uk PDFs
        text = re.sub(r"(?mi)^.*Status:\s*This (?:is|version).*$", "", text)
        text = re.sub(r"(?mi)^.*Changes to legislation:.*$", "", text)

        # Explanatory notes markers
        text = re.sub(r"(?mi)^EXPLANATORY NOTES$", "", text)
        text = re.sub(r"(?mi)^These notes refer to.*$", "", text)

        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()