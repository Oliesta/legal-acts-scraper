# Legal Acts Scraper (PDF-First)

Python framework for extracting legal acts from PDF documents across ZA, GB, US, and AU jurisdictions. Uses a local LLM (Gemma via Ollama) to parse PDF text into structured sections. Outputs JSON matching the Dala bulk-import schema.

## Why PDF-first?

Most government legislation is published as PDF. Trying to parse HTML is fragile. This framework:

1. Downloads the PDF (or reads a local file you already have)
2. Extracts raw text via `pdftotext` / `pypdf`
3. Sends text to a **local Gemma model** (via Ollama) to extract structured sections
4. Validates output against the Dala import schema
5. Writes clean JSON ready for bulk import

## Setup

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Ollama + Gemma
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3          # or gemma3:12b for better quality
ollama serve                # if not auto-started

# 3. System PDF tools
sudo apt install poppler-utils    # Ubuntu/Debian
# or: brew install poppler        # macOS
```

## Usage

### Configure URLs/paths in config.py

```python
# PDF URL — will be downloaded
{"source": "url", "url": "https://example.gov.za/act.pdf", "short_name": "CPA", ...}

# Local file
{"source": "file", "path": "./pdfs/insurance_act.pdf", "short_name": "IA", ...}
```

### Run

```bash
python run_scraper.py --country ZA
python run_scraper.py --all
python run_scraper.py --country ZA --model gemma3:12b
python run_scraper.py --folder ./pdfs/za --country ZA --category insurance
```

### Output → `output/*.json` → Upload to Dala admin → Import JSON