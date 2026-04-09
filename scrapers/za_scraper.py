"""
South Africa scraper.

SA legislation PDFs come from Government Gazette, SAFLII, Acts Online, etc.
They often have gazette boilerplate, dual-language headers, and
irregular formatting. This scraper adds SA-specific text cleanup
before sending to the LLM.
"""

from __future__ import annotations

import re
from pathlib import Path

from base_scraper import BaseScraper


class ZAScraper(BaseScraper):
    country_code = "ZA"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with SA-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_za_text(raw)

    @staticmethod
    def _clean_za_text(text: str) -> str:
        """Remove SA Government Gazette artifacts."""
        # Remove gazette header blocks
        text = re.sub(
            r"(?mi)^.*(?:GOVERNMENT GAZETTE|STAATSKOERANT|REPUBLIC OF SOUTH AFRICA).*$",
            "",
            text,
        )
        # Remove gazette number lines
        text = re.sub(r"(?mi)^.*No\.\s*\d+\s*GOVERNMENT GAZETTE.*$", "", text)
        text = re.sub(r"(?mi)^.*Vol\.\s*\d+.*Pretoria.*$", "", text)

        # Remove Afrikaans headers that sometimes interleave
        # (legislation PDFs sometimes have EN/AF side by side)
        # Only strip if clearly gazette boilerplate
        text = re.sub(r"(?mi)^.*ALGEMENE KENNISGEWING.*$", "", text)
        text = re.sub(r"(?mi)^.*GENERAL NOTICE.*$", "", text)

        # Remove page footers with gazette references
        text = re.sub(r"(?mi)^.*This gazette is also available.*$", "", text)
        text = re.sub(r"(?mi)^.*Hierdie koerant is ook beskikbaar.*$", "", text)

        # Clean up excessive whitespace from removals
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()