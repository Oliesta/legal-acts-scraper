#!/usr/bin/env python3
"""
CLI entry point for the legal acts PDF scraper.

Usage:
    python run_scraper.py --country ZA
    python run_scraper.py --all
    python run_scraper.py --country ZA --model gemma3:12b
    python run_scraper.py --folder ./pdfs/za --country ZA --category insurance
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from config import COUNTRY_CONFIGS, DEFAULT_MODEL, GEMINI_DEFAULT_MODEL, GROQ_DEFAULT_MODEL, OUTPUT_DIR
from llm_extractor import LLMExtractor
from scrapers import AUScraper, GBScraper, INScraper, USScraper, ZAScraper

console = Console()

SCRAPER_MAP = {
    "ZA": ZAScraper,
    "GB": GBScraper,
    "US": USScraper,
    "AU": AUScraper,
    "IN": INScraper,
}


def build_configs_from_folder(
    folder: str, country: str, category: str
) -> list[dict]:
    """
    Build act configs from a folder of PDFs.
    Each PDF becomes one act entry. Metadata will be extracted by the LLM.
    """
    folder_path = Path(folder)
    if not folder_path.is_dir():
        console.print(f"[red]Folder not found: {folder}[/red]")
        return []

    pdfs = sorted(folder_path.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]No PDF files found in {folder}[/yellow]")
        return []

    console.print(f"[cyan]Found {len(pdfs)} PDF(s) in {folder}[/cyan]")

    configs = []
    for pdf in pdfs:
        # Derive short_name as initials of meaningful words in the filename
        stem = pdf.stem
        words = re.split(r"[\s\-_]+", stem)
        # Take first letter of each word that's not a number and not a stop word
        stop = {"of", "the", "and", "no", "act", "a", "an"}
        initials = "".join(
            w[0].upper() for w in words if w and w.lower() not in stop and not w.isdigit()
        )
        short = initials[:6] or stem[:6].upper()

        configs.append({
            "source": "file",
            "path": str(pdf),
            "short_name": short,
            "category": category,
            # act_number, effective_date, description → extracted by LLM
        })

    return configs


def run_country(
    country: str, llm: LLMExtractor, extra_configs: list[dict] | None = None
) -> list[dict]:
    """Run scraper for a single country."""
    country = country.upper()
    if country not in SCRAPER_MAP:
        console.print(f"[red]Unknown country: {country}. Use: ZA, GB, US, AU, IN[/red]")
        return []

    configs = extra_configs or COUNTRY_CONFIGS.get(country, [])
    if not configs:
        console.print(
            f"[yellow]No acts configured for {country}. "
            f"Edit config.py or use --folder.[/yellow]"
        )
        return []

    scraper = SCRAPER_MAP[country](configs, llm=llm)
    results = scraper.run()
    scraper.save()

    if scraper.errors:
        console.print(f"\n[bold red]Errors ({country}):[/bold red]")
        for err in scraper.errors:
            console.print(f"  [red]• {err}[/red]")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scrape legal acts from PDFs for Dala bulk import"
    )
    parser.add_argument("--country", type=str, help="Country code: ZA, GB, US, AU, IN")
    parser.add_argument("--all", action="store_true", help="Scrape all configured countries")
    parser.add_argument("--model", type=str, help="Model name (default depends on provider)")
    parser.add_argument("--folder", type=str, help="Folder of PDFs to process")
    parser.add_argument("--category", type=str, default="general", help="Category for --folder mode (default: general)")
    parser.add_argument("--output", type=str, help="Custom output filename")
    parser.add_argument("--groq", action="store_true", help="Use Groq API instead of Ollama (reads GROQ_API_KEY env var)")
    parser.add_argument("--gemini", action="store_true", help="Use Google Gemini API (reads GEMINI_API_KEY env var)")
    args = parser.parse_args()

    if not args.country and not args.all and not args.folder:
        parser.print_help()
        sys.exit(1)

    # Require --country with --folder
    if args.folder and not args.country:
        console.print("[red]--folder requires --country[/red]")
        sys.exit(1)

    # Determine provider and API key
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    use_gemini = args.gemini or bool(gemini_api_key)
    use_groq = args.groq or (bool(groq_api_key) and not use_gemini)

    if use_gemini:
        if not gemini_api_key:
            console.print(
                "[bold red]GEMINI_API_KEY not set.[/bold red]\n"
                "Get a free key: https://aistudio.google.com/apikey\n"
                "Then: export GEMINI_API_KEY=AIza..."
            )
            sys.exit(1)
        model = args.model or GEMINI_DEFAULT_MODEL
        llm = LLMExtractor(model=model, provider="gemini", api_key=gemini_api_key)
        console.print(f"[bold cyan]LLM: {model}[/bold cyan] (via Gemini — 1M TPM free tier)")
    elif use_groq:
        if not groq_api_key:
            console.print(
                "[bold red]GROQ_API_KEY not set.[/bold red]\n"
                "Export it: export GROQ_API_KEY=gsk_..."
            )
            sys.exit(1)
        model = args.model or GROQ_DEFAULT_MODEL
        llm = LLMExtractor(model=model, provider="groq", api_key=groq_api_key)
        console.print(f"[bold cyan]LLM: {model}[/bold cyan] (via Groq)")
    else:
        model = args.model or DEFAULT_MODEL
        llm = LLMExtractor(model=model)
        console.print(f"[bold cyan]LLM: {model}[/bold cyan] (via Ollama)")

        # Test Ollama connectivity
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            if model not in models and f"{model}:latest" not in models:
                console.print(
                    f"[yellow]Warning: model '{model}' not found in Ollama. "
                    f"Available: {', '.join(models) or 'none'}[/yellow]"
                )
                console.print(f"[yellow]Run: ollama pull {model}[/yellow]")
        except Exception:
            console.print(
                "[bold red]Cannot connect to Ollama![/bold red]\n"
                "Start it with: ollama serve\n"
                "Then pull a model: ollama pull gemma4:e4b\n"
                "Or use Gemini (recommended): export GEMINI_API_KEY=AIza... then re-run with --gemini"
            )
            sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Folder mode ─────────────────────────────────────────────────
    if args.folder:
        configs = build_configs_from_folder(args.folder, args.country, args.category)
        results = run_country(args.country, llm, extra_configs=configs)
        _print_summary(results)
        return

    # ── All countries ───────────────────────────────────────────────
    if args.all:
        console.print("[bold]Scraping all configured countries[/bold]\n")
        all_results = []
        for country in ["ZA", "GB", "US", "AU", "IN"]:
            results = run_country(country, llm)
            all_results.extend(results)

        if all_results:
            merged_name = args.output or "all_acts.json"
            merged_path = Path(OUTPUT_DIR) / merged_name
            with open(merged_path, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            console.print(f"\n[bold green]Merged: {len(all_results)} acts → {merged_path}[/bold green]")

        _print_summary(all_results)
        return

    # ── Single country ──────────────────────────────────────────────
    results = run_country(args.country, llm)
    _print_summary(results)


def _print_summary(results: list[dict]):
    """Print a summary table."""
    if not results:
        console.print("\n[yellow]No acts were extracted.[/yellow]")
        return

    table = Table(title="Scraped Acts Summary")
    table.add_column("Country", style="bold")
    table.add_column("Short Name", style="cyan")
    table.add_column("Act Number")
    table.add_column("Category")
    table.add_column("Sections", justify="right")

    for act in results:
        table.add_row(
            act["country"],
            act["shortName"],
            act["actNumber"],
            act["category"],
            str(len(act.get("sections", []))),
        )

    console.print(table)
    console.print(
        f"\n[bold]Total: {len(results)} acts, "
        f"{sum(len(a.get('sections', [])) for a in results)} sections[/bold]"
    )
    console.print(
        f"[dim]Upload JSON from {OUTPUT_DIR}/ to Dala admin → Import JSON[/dim]"
    )


if __name__ == "__main__":
    main()