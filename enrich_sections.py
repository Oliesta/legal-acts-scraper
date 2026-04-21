#!/usr/bin/env python3
"""
Post-process scraped output JSON to add tags and keyProvisions to every section.

Usage:
    python enrich_sections.py --country ZA
    python enrich_sections.py --all
    python enrich_sections.py output/ZA_acts.json

Requires GEMINI_API_KEY env var (auto-detected) or GROQ_API_KEY with --groq.
Skips sections that already have non-empty tags (safe to re-run).
Saves progress after each act.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from rich.console import Console

console = Console()

BATCH_SIZE = 15  # sections per LLM call

ENRICH_PROMPT = """\
For each numbered legal section below, extract:
- tags: 5-10 lowercase keyword strings describing the legal concepts, topics, and affected parties \
(e.g. "liability", "consumer rights", "insurance premium", "employer obligations")
- keyProvisions: 3-6 short plain-language strings summarising the key obligations, rights, or \
penalties in this section (e.g. "Insurer must pay claims within 30 days", \
"Consumer may cancel within 5 business days without penalty")

Return ONLY a JSON array with one object per section, in the same order:
[{{"tags": [...], "keyProvisions": [...]}}, ...]

Sections:
{sections_block}"""


def _build_sections_block(sections: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sections, 1):
        title = (s.get("title") or "").strip()
        content = (s.get("content") or "")[:3000]
        parts.append(f"[{i}] Title: {title}\nContent: {content}")
    return "\n\n".join(parts)


def _extract_json_array(text: str) -> list | None:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


# ── LLM callers ─────────────────────────────────────────────────────

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    from google import genai

    client = genai.Client(api_key=api_key)
    for attempt in range(4):
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return resp.text
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "503" in msg or "unavailable" in msg.lower():
                wait = 10 * (2**attempt)
                console.print(f"  [yellow]Gemini {msg[:80]} — retrying in {wait}s[/yellow]")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini: max retries exceeded")


def _call_groq(prompt: str, api_key: str, model: str) -> str:
    from groq import Groq, RateLimitError

    client = Groq(api_key=api_key)
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            return resp.choices[0].message.content
        except RateLimitError:
            wait = 15 * (2**attempt)
            console.print(f"  [yellow]Groq rate limit — retrying in {wait}s[/yellow]")
            time.sleep(wait)
    raise RuntimeError("Groq: max retries exceeded")


# ── Core enrichment ─────────────────────────────────────────────────

def enrich_file(file_path: Path, call_fn, batch_size: int = BATCH_SIZE) -> None:
    with open(file_path, encoding="utf-8") as f:
        acts = json.load(f)

    for act_idx, act in enumerate(acts, 1):
        short = act.get("shortName", f"act{act_idx}")
        sections = act.get("sections", [])

        pending = [i for i, s in enumerate(sections) if not s.get("tags")]
        if not pending:
            console.print(f"  [dim]{short}: all {len(sections)} sections already enriched — skipping[/dim]")
            continue

        console.print(
            f"\n[bold]{short}[/bold] ({act_idx}/{len(acts)}) — "
            f"enriching {len(pending)} of {len(sections)} sections"
        )

        for batch_start in range(0, len(pending), batch_size):
            batch_indices = pending[batch_start : batch_start + batch_size]
            batch_sections = [sections[i] for i in batch_indices]

            console.print(
                f"  Batch {batch_start // batch_size + 1}: "
                f"sections {batch_indices[0] + 1}–{batch_indices[-1] + 1}"
            )

            try:
                raw = call_fn(ENRICH_PROMPT.format(sections_block=_build_sections_block(batch_sections)))
                results = _extract_json_array(raw)
                if not isinstance(results, list) or len(results) != len(batch_indices):
                    console.print(
                        f"  [red]Unexpected result count "
                        f"({len(results) if isinstance(results, list) else 'None'} "
                        f"vs {len(batch_indices)}) — skipping batch[/red]"
                    )
                    continue
                for idx, result in zip(batch_indices, results):
                    sections[idx]["tags"] = result.get("tags") or []
                    sections[idx]["keyProvisions"] = result.get("keyProvisions") or []
            except Exception as e:
                console.print(f"  [red]Batch failed: {e}[/red]")
                continue

            time.sleep(1)

        # Save after every act so progress survives an interruption
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(acts, f, ensure_ascii=False, indent=2)
        console.print(f"  [green]Saved → {file_path}[/green]")


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    from config import COUNTRY_CONFIGS, GEMINI_DEFAULT_MODEL, GROQ_DEFAULT_MODEL, OUTPUT_DIR

    parser = argparse.ArgumentParser(description="Add tags and keyProvisions to scraped section JSON")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--country", metavar="CC", help="Two-letter country code (ZA, GB, US, AU, IN)")
    target.add_argument("--all", action="store_true", dest="all_countries", help="All countries")
    parser.add_argument("file", nargs="?", help="Path to a specific output JSON file")
    parser.add_argument("--gemini", action="store_true")
    parser.add_argument("--groq", action="store_true")
    parser.add_argument("--model", help="Override model name")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, metavar="N",
                        help=f"Sections per LLM call (default {BATCH_SIZE})")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    use_gemini = args.gemini or (gemini_key and not args.groq)
    use_groq = args.groq and not use_gemini

    if use_gemini:
        if not gemini_key:
            console.print("[red]GEMINI_API_KEY not set — get a free key at aistudio.google.com/apikey[/red]")
            sys.exit(1)
        model = args.model or GEMINI_DEFAULT_MODEL
        call_fn = lambda p: _call_gemini(p, gemini_key, model)
        console.print(f"[cyan]Provider: Gemini ({model})[/cyan]")
    elif use_groq:
        if not groq_key:
            console.print("[red]GROQ_API_KEY not set[/red]")
            sys.exit(1)
        model = args.model or GROQ_DEFAULT_MODEL
        call_fn = lambda p: _call_groq(p, groq_key, model)
        console.print(f"[cyan]Provider: Groq ({model})[/cyan]")
    else:
        console.print("[red]No LLM provider. Set GEMINI_API_KEY or pass --groq.[/red]")
        sys.exit(1)

    if args.file:
        files = [Path(args.file)]
    elif args.all_countries:
        files = [Path(OUTPUT_DIR) / f"{cc}_acts.json" for cc in COUNTRY_CONFIGS]
    elif args.country:
        files = [Path(OUTPUT_DIR) / f"{args.country.upper()}_acts.json"]
    else:
        parser.print_help()
        sys.exit(1)

    for fp in files:
        if not fp.exists():
            console.print(f"[yellow]Not found — skipping: {fp}[/yellow]")
            continue
        console.print(f"\n[bold blue]── {fp} ──[/bold blue]")
        enrich_file(fp, call_fn, args.batch_size)

    console.print("\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()
