# Legal Acts Scraper (PDF-First)

Python framework for extracting legal acts from PDF documents across ZA, GB, US, AU, and IN jurisdictions. Uses an LLM (local Gemma via Ollama, Google Gemini, or Groq) to parse PDF text into structured sections. Outputs JSON matching the Dala bulk-import schema.

## Why PDF-first?

Most government legislation is published as PDF. Trying to parse HTML is fragile. This framework:

1. Downloads the PDF (or reads a local file you already have)
2. Extracts raw text using a 4-layer stack (best → fallback)
3. Sends text to an LLM (local Gemma via Ollama, Google Gemini, or Groq) to extract structured sections
4. Validates output against the Dala import schema
5. Writes clean JSON ready for bulk import

## Extraction stack

| Method | Library | Platform | Notes |
|---|---|---|---|
| `pdftotext` | poppler (system) | Linux/macOS/Win* | Best quality, layout-aware |
| `pdfplumber` | Python package | All | Structured fallback, no binaries |
| `pypdf` | Python package | All | Basic fallback |
| `tesseract` | system binary | Linux/macOS/Win* | OCR for scanned PDFs only |

\* Requires a manual install on Windows — see setup below.

---

## Gemini (recommended — free, 1M TPM, no GPU needed)

Google Gemini Flash has a free tier with 1 million tokens per minute — enough to finish a full 5-country run in ~30 minutes. ZA's largest act (514k chars) becomes 5 chunks instead of 91.

**1. Get a free API key** at https://aistudio.google.com/apikey → Create API key

**2. Install deps and set key**
```bash
pip install -r requirements.txt   # includes google-genai
export GEMINI_API_KEY=AIza...     # add to ~/.bashrc to make permanent
```

**3. Run**
```bash
python run_scraper.py --country ZA --gemini
python run_scraper.py --all --gemini
```

The key is auto-detected: if `GEMINI_API_KEY` is set in the environment, `--gemini` is implied. Default model is `gemini-2.0-flash-lite`.

---

## Groq (alternative — free but 100k tokens/day limit)

Groq's free tier burns out after ~1 act. Only useful for small one-off tests.

```bash
export GROQ_API_KEY=gsk_...
python run_scraper.py --country ZA --groq
```

---

## Setup (local Ollama)

### Linux / macOS

```bash
# 1. Install Python 3.10+ and pip (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
# macOS (if not already installed via Xcode tools):
# brew install python

# 2. Clone the repo
git clone -b claude/review-scraping-strategy-iBUTW https://github.com/oliesta/legal-acts-scraper.git
cd legal-acts-scraper

# 3. Create a virtual environment and install Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Ollama + Gemma
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4:e4b      # 9.6GB — good balance of speed and quality
# or for best quality (needs 32GB+ RAM):
# ollama pull gemma4:26b   # 18GB — best extraction quality
ollama serve                # if not auto-started

# 5. System PDF tools
sudo apt install poppler-utils tesseract-ocr   # Ubuntu/Debian
# or:
brew install poppler tesseract                  # macOS
```

### Windows

pdfplumber and pypdf are pure Python and work out of the box. The steps below add the faster `pdftotext` and OCR support.

**Step 1 — Install Python 3.10+**

Download and install from https://www.python.org/downloads/ — tick **Add Python to PATH** during install.

Verify:
```bat
python --version
pip --version
```

**Step 2 — Clone the repo and install Python deps**
```bat
git clone -b claude/review-scraping-strategy-iBUTW https://github.com/oliesta/legal-acts-scraper.git
cd legal-acts-scraper
pip install -r requirements.txt
```

**Step 2 — Ollama**

Download and run the installer from https://ollama.com/download, then:
```bat
ollama pull gemma4:e4b
ollama serve
```

**Step 3 — Poppler (for pdftotext + OCR)**

1. Download the latest release from https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to e.g. `C:\poppler`
3. Add `C:\poppler\Library\bin` to your `PATH`:
   - System Properties → Environment Variables → Path → Edit → New

**Step 4 — Tesseract (for OCR on scanned PDFs)**

1. Download the installer from https://github.com/UB-Mannheim/tesseract/wiki
2. During install, tick **Add to PATH** (or add `C:\Program Files\Tesseract-OCR` manually)
3. The scraper will auto-detect the default install path even if PATH is not set

**Verify everything works:**
```bat
pdftotext -v
tesseract --version
ollama list
```

---

## Usage

### Configure URLs/paths in `config.py`

```python
# PDF URL — will be downloaded and cached
{"source": "url", "url": "https://example.gov.za/act.pdf", "short_name": "CPA", ...}

# Local file
{"source": "file", "path": "./pdfs/insurance_act.pdf", "short_name": "IA", ...}
```

### Run

```bash
# Single country (Gemini — recommended)
export GEMINI_API_KEY=AIza...
python run_scraper.py --country ZA --gemini
python run_scraper.py --all --gemini

# Single country (Ollama)
python run_scraper.py --country ZA

# Single country (Groq)
export GROQ_API_KEY=gsk_...
python run_scraper.py --country ZA --groq

# Override model
python run_scraper.py --country ZA --model gemma4:26b                    # Ollama
python run_scraper.py --country ZA --groq --model llama-3.1-8b-instant  # Groq

# Process a folder of local PDFs
python run_scraper.py --folder ./pdfs/za --country ZA --category insurance
```

### Output → `output/*.json` → Upload to Dala admin → Import JSON

---

## Enrich sections with tags and keyProvisions

After scraping, run `enrich_sections.py` to add two extra fields to every section:

| Field | Type | Description |
|---|---|---|
| `tags` | `string[]` | 5–10 lowercase keyword strings (legal concepts, topics, affected parties) |
| `keyProvisions` | `string[]` | 3–6 plain-language strings summarising key obligations, rights, or penalties |

Sections that already have `tags` are skipped, so the script is safe to re-run after an interruption.

```bash
# Single country (Gemini — recommended)
python enrich_sections.py --country ZA

# All countries
python enrich_sections.py --all

# Specific file
python enrich_sections.py output/ZA_acts.json

# With Groq (100k token/day limit — only practical for small runs)
python enrich_sections.py --country ZA --groq

# Override model or batch size
python enrich_sections.py --all --model gemini-2.0-flash-lite --batch-size 10
```

The script batches 15 sections per LLM call (configurable via `--batch-size`) to minimise API quota usage, and saves the JSON after each act so progress is never lost.

**Typical output for one section:**
```json
{
  "title": "Insurer's duty to pay",
  "content": "...",
  "tags": ["claims settlement", "payment obligation", "insurance", "policyholder rights", "dispute resolution"],
  "keyProvisions": [
    "Insurer must settle valid claims within 10 business days of receiving all required documents",
    "Failure to pay within the prescribed period entitles the policyholder to statutory interest",
    "Disputes may be referred to the Ombud without first exhausting internal processes"
  ]
}
```

---

## Auto-generate metadata

Use `auto_metadata.py` to generate a config entry from a PDF and optionally append it to `config.py`:

```bash
# Print generated entry
python auto_metadata.py --pdf https://example.org/act.pdf --country ZA

# Write directly into config.py
python auto_metadata.py --pdf ./pdfs/act.pdf --country ZA --write
```

---

## Local development (git workflow)

### Clone the repo

Always clone the active branch — `main` may be behind:

```bash
git clone -b claude/review-scraping-strategy-iBUTW https://github.com/oliesta/legal-acts-scraper.git
cd legal-acts-scraper
pip install -r requirements.txt
```

### Pull latest changes

```bash
git pull origin claude/review-scraping-strategy-iBUTW
```

### Work on a feature or fix

```bash
# Create a new branch off the current one
git checkout -b my-feature

# Make your changes, then stage and commit
git add config.py run_scraper.py   # add specific files
git commit -m "Add NZ jurisdiction config"

# Push branch to GitHub
git push -u origin my-feature
```

### Keep your branch up to date

```bash
git fetch origin
git merge origin/claude/review-scraping-strategy-iBUTW
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `pdftotext not found` | Install poppler (see setup above) |
| `UnicodeDecodeError` from pdftotext | Fixed in current version — encoding is forced to UTF-8 |
| Console window flashes on Windows | Fixed in current version — subprocess windows are suppressed |
| `TesseractNotFoundError` | Install Tesseract; scraper auto-checks `C:\Program Files\Tesseract-OCR` |
| `Cannot connect to Ollama` | Run `ollama serve`, or use Gemini: `export GEMINI_API_KEY=AIza... && python run_scraper.py --gemini` |
| `model 'gemma4:e4b' not found` | Run `ollama pull gemma4:e4b` |
| `GEMINI_API_KEY not set` | Get free key at aistudio.google.com/apikey, then `export GEMINI_API_KEY=AIza...` |
| Groq 429 / 100k TPD limit hit | Groq free tier only allows 100k tokens/day — switch to Gemini (`--gemini`) |
| `ValidationError: effectiveDate` | Add `"effective_date": "YYYY-MM-DD"` to the act config |
| `enrich_sections.py` — unexpected result count | LLM merged or split sections in its response; the batch is skipped and re-runnable |
