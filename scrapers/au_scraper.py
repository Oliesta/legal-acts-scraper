"""
Australia scraper.

AU legislation PDFs from legislation.gov.au (Federal Register),
AustLII, and state-level sources. Cleans up compilation notes,
Federal Register headers, and endnote tables.
"""

from __future__ import annotations

import re
from pathlib import Path

from base_scraper import BaseScraper


class AUScraper(BaseScraper):
    country_code = "AU"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with AU-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_au_text(raw)

    @staticmethod
    def _clean_au_text(text: str) -> str:
        """Remove AU legislation PDF artifacts."""
        # Federal Register compilation headers
        text = re.sub(r"(?mi)^.*Compilation No\.\s*\d+.*$", "", text)
        text = re.sub(r"(?mi)^.*Includes amendments up to:.*$", "", text)
        text = re.sub(r"(?mi)^.*Registered:.*$", "", text)
        text = re.sub(r"(?mi)^.*Authorised Version.*$", "", text)

        # Compilation/endnote tables
        text = re.sub(r"(?mi)^.*Endnote \d+.*$", "", text)
        text = re.sub(r"(?mi)^.*Table of Instruments.*$", "", text)

        # Commonwealth coat of arms alt text
        text = re.sub(r"(?mi)^.*Commonwealth of Australia.*Coat of Arms.*$", "", text)

        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()