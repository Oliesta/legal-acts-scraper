"""
India scraper.

Indian legislation PDFs come from:
  - indiacode.nic.in (India Code — primary source, maintained by Legislative Dept)
  - legislative.gov.in (Legislative Department)
  - egazette.gov.in (Gazette of India)
  - prsindia.org (PRS Legislative Research — clean PDFs)
  - State legislature sites for state-level acts

Indian acts have specific formatting:
  - "THE [NAME] ACT, [YEAR]" title convention
  - "No. X of YYYY" act numbering
  - Sections numbered as "1.", "2.", etc. with marginal headings
  - "Provided that..." provisos are common
  - Schedules and annexures at the end
  - Gazette of India notifications have heavy boilerplate
  - Hindi/English bilingual headers in gazette PDFs
"""

from __future__ import annotations

import re
from pathlib import Path

from base_scraper import BaseScraper


class INScraper(BaseScraper):
    country_code = "IN"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with India-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_in_text(raw)

    @staticmethod
    def _clean_in_text(text: str) -> str:
        """Remove Indian legislation PDF artifacts."""

        # ── Gazette of India boilerplate ────────────────────────────
        # Hindi headers (Devanagari script gazette titles)
        text = re.sub(r"(?m)^.*\u092D\u093E\u0930\u0924\s*\u0915\u093E\s*\u0930\u093E\u091C\u092A\u0924\u094D\u0930.*$", "", text)
        # "THE GAZETTE OF INDIA" header
        text = re.sub(r"(?mi)^.*THE GAZETTE OF INDIA.*$", "", text)
        text = re.sub(r"(?mi)^.*EXTRAORDINARY.*$", "", text)
        # "PART II — Section 1" gazette section markers
        text = re.sub(r"(?mi)^.*PART\s+II\s*[—–-]\s*Section\s+\d+.*$", "", text)
        # "MINISTRY OF..." notification headers
        text = re.sub(r"(?mi)^.*MINISTRY OF LAW AND JUSTICE.*$", "", text)
        text = re.sub(r"(?mi)^.*\(Legislative Department\).*$", "", text)

        # ── Gazette publication metadata ────────────────────────────
        # "New Delhi, the Xth Month, YYYY" date lines
        text = re.sub(r"(?mi)^.*New Delhi,?\s*the\s+\d+.*$", "", text)
        # "REGISTERED NO." lines
        text = re.sub(r"(?mi)^.*REGISTERED\s+NO\..*$", "", text)
        # "RNI No." lines
        text = re.sub(r"(?mi)^.*RNI\s+No\..*$", "", text)
        # "[No. XXX]" gazette notification numbers
        text = re.sub(r"(?m)^\s*\[No\.\s*\d+[A-Z]?\].*$", "", text)

        # ── India Code / indiacode.nic.in artifacts ─────────────────
        text = re.sub(r"(?mi)^.*indiacode\.nic\.in.*$", "", text)
        text = re.sub(r"(?mi)^.*India Code.*$", "", text)

        # ── Common footer patterns ──────────────────────────────────
        # Page numbers with gazette references
        text = re.sub(r"(?mi)^.*SEC\.\s*\d+\]\s*THE GAZETTE.*$", "", text)
        # "Printed by the Manager" footer
        text = re.sub(r"(?mi)^.*Printed by the Manager.*$", "", text)
        # Government of India Press
        text = re.sub(r"(?mi)^.*Government of India Press.*$", "", text)

        # ── Amendment notation cleanup ──────────────────────────────
        # "[Vide Notification No. ...]" inline references — keep but clean
        # Footnote markers like "1[", "2[" from amendment insertions
        text = re.sub(r"(\d+)\[", r"[\1: ", text)

        # ── Hindi text removal (optional — gazette PDFs are bilingual) ──
        # Remove lines that are predominantly Devanagari
        # (keeps English text, removes Hindi duplicates in bilingual PDFs)
        text = re.sub(
            r"(?m)^[\u0900-\u097F\s\u0964\u0965.,;:!?\-()]+$",
            "",
            text,
        )

        # Clean up excessive whitespace from removals
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()