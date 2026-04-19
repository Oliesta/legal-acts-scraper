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

# Distinctly Afrikaans words that don't appear in English legal text.
# Two or more hits on a single line = Afrikaans line, drop it.
_AF_WORDS = re.compile(
    r"\b(bedoel|bedoelde|beteken|ingevolge|kragtens|hierdie|toepassing|"
    r"versekeraar|versekeringsbedryf|paragraaf|uitvoerende|maatskappy|"
    r"skedule|herstelskema|herversekering|kennisgewing|bepaling|"
    r"wetgewing|beleid|beampte)\b",
    re.IGNORECASE,
)


class ZAScraper(BaseScraper):
    country_code = "ZA"

    def extract_text(self, pdf_path: Path) -> str:
        """Extract text with SA-specific cleanup."""
        raw = super().extract_text(pdf_path)
        return self._clean_za_text(raw)

    @staticmethod
    def _clean_za_text(text: str) -> str:
        """Remove SA Government Gazette artifacts and Afrikaans content."""
        # ── Gazette boilerplate ──────────────────────────────────────
        text = re.sub(
            r"(?mi)^.*(?:GOVERNMENT GAZETTE|STAATSKOERANT|REPUBLIC OF SOUTH AFRICA).*$",
            "",
            text,
        )
        text = re.sub(r"(?mi)^.*No\.\s*\d+\s*GOVERNMENT GAZETTE.*$", "", text)
        text = re.sub(r"(?mi)^.*Vol\.\s*\d+.*Pretoria.*$", "", text)
        text = re.sub(r"(?mi)^.*ALGEMENE KENNISGEWING.*$", "", text)
        text = re.sub(r"(?mi)^.*GENERAL NOTICE.*$", "", text)
        text = re.sub(r"(?mi)^.*This gazette is also available.*$", "", text)
        text = re.sub(r"(?mi)^.*Hierdie koerant is ook beskikbaar.*$", "", text)

        # ── Pass 1: Afrikaans definition entries ─────────────────────
        # SA PDFs publish definitions bilingually. Each definition appears
        # as: "term" means ... (English) then "term" bedoel/beteken ... (Afrikaans).
        # Strip entries where the connecting verb is Afrikaans.
        text = re.sub(
            r'["\u2018\u2019]{1,2}[^"\u2018\u2019\n]{1,80}["\u2018\u2019]{1,2}'
            r'[^;.\n]*?\b(?:bedoel|bedoelde|beteken)\b[^;.\n]*[;.]?',
            "",
            text,
            flags=re.IGNORECASE,
        )

        # ── Pass 2: Line-level Afrikaans filter ──────────────────────
        # If a line scores 2+ distinctive Afrikaans words, it's Afrikaans — drop it.
        clean_lines = []
        for line in text.splitlines():
            if len(_AF_WORDS.findall(line)) >= 2:
                continue
            clean_lines.append(line)
        text = "\n".join(clean_lines)

        # ── Whitespace cleanup ───────────────────────────────────────
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()
