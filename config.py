"""
Scraper configuration — add your PDF URLs or local file paths here.

Each act entry needs:
  - source: "url" (download PDF) or "file" (local path)
  - url or path: the PDF location
  - short_name, act_number, category, effective_date: metadata
  - description: optional (Gemma can generate from content if omitted)
"""

# ─── Request settings ───────────────────────────────────────────────
REQUEST_TIMEOUT = 60  # PDFs can be large
REQUEST_DELAY = 2.0
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ─── LLM settings ──────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3"  # or "gemma3:12b" for better quality
CHUNK_SIZE = 6000         # chars per LLM chunk (stay within context window)
CHUNK_OVERLAP = 500       # overlap between chunks to avoid splitting sections

# ─── Output ─────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
PDF_CACHE_DIR = "pdf_cache"  # downloaded PDFs are cached here

# ─── South Africa ───────────────────────────────────────────────────
ZA_ACTS = [
    # EXAMPLE — PDF from URL:
    # {
    #     "source": "url",
    #     "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act68of2008.pdf",
    #     "short_name": "CPA",
    #     "act_number": "68 of 2008",
    #     "category": "consumer",
    #     "effective_date": "2009-04-24",
    #     "description": "Promotes a fair, accessible and sustainable marketplace for consumer products and services.",
    # },
    #
    # EXAMPLE — local PDF file:
    # {
    #     "source": "file",
    #     "path": "./pdfs/za/insurance_act_18_of_2017.pdf",
    #     "short_name": "IA",
    #     "act_number": "18 of 2017",
    #     "category": "insurance",
    #     "effective_date": "2018-07-01",
    #     "description": "Regulates the insurance industry in South Africa.",
    # },
]

# ─── United Kingdom ─────────────────────────────────────────────────
GB_ACTS = [
    # UK legislation PDFs from legislation.gov.uk:
    # {
    #     "source": "url",
    #     "url": "https://www.legislation.gov.uk/ukpga/2015/15/data.pdf",
    #     "short_name": "CRA",
    #     "act_number": "2015 c. 15",
    #     "category": "consumer",
    #     "effective_date": "2015-10-01",
    #     "description": "Sets out consumer rights regarding goods, services, and digital content.",
    # },
]

# ─── United States ──────────────────────────────────────────────────
US_ACTS = [
    # US legislation from congress.gov or GPO:
    # {
    #     "source": "url",
    #     "url": "https://www.govinfo.gov/content/pkg/PLAW-111publ203/pdf/PLAW-111publ203.pdf",
    #     "short_name": "TILA",
    #     "act_number": "Pub.L. 90-321",
    #     "category": "credit",
    #     "effective_date": "1968-07-01",
    #     "description": "Requires lenders to provide standardized information about loan terms.",
    # },
]

# ─── Australia ──────────────────────────────────────────────────────
AU_ACTS = [
    # AU legislation from legislation.gov.au:
    # {
    #     "source": "url",
    #     "url": "https://www.legislation.gov.au/C2004A00109/latest/download",
    #     "short_name": "CCA",
    #     "act_number": "No. 51, 1974",
    #     "category": "consumer",
    #     "effective_date": "2011-01-01",
    #     "description": "Competition and consumer protection legislation.",
    # },
]

# ─── India ──────────────────────────────────────────────────────────
IN_ACTS = [
    # Indian legislation from indiacode.nic.in or legislative.gov.in:
    # {
    #     "source": "url",
    #     "url": "https://www.indiacode.nic.in/bitstream/123456789/2058/1/AAA2019____19.pdf",
    #     "short_name": "CPA2019",
    #     "act_number": "35 of 2019",
    #     "category": "consumer",
    #     "effective_date": "2020-07-20",
    #     "description": "Protects consumer interests and establishes consumer dispute redressal commissions.",
    # },
    #
    # Local PDF:
    # {
    #     "source": "file",
    #     "path": "./pdfs/in/insurance_act_1938.pdf",
    #     "short_name": "IA1938",
    #     "act_number": "4 of 1938",
    #     "category": "insurance",
    #     "effective_date": "1938-03-03",
    #     "last_amended": "2015-01-01",
    #     "description": "Regulates insurance business in India.",
    # },
]

# ─── Registry ──────────────────────────────────────────────────────
COUNTRY_CONFIGS = {
    "ZA": ZA_ACTS,
    "GB": GB_ACTS,
    "US": US_ACTS,
    "AU": AU_ACTS,
    "IN": IN_ACTS,
}