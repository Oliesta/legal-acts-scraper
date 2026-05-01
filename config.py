"""
Scraper configuration — add your PDF URLs or local file paths here.

Each act entry needs:
  - source: "url" (download PDF) or "file" (local path)
  - url or path: the PDF location
  - short_name, act_number, category, effective_date: metadata
  - description: optional (LLM can generate from content if omitted)

Optional:
  - target_sections: list of section numbers to keep after extraction
      (e.g. ["185", "186"]). The scraper extracts ALL sections first,
      then discards any whose number is not in this list. Use this to
      avoid importing hundreds of procedural/administrative sections when
      you only need the rights-granting ones. The rule of thumb: keep
      sections that say "no person may…", "every employee is entitled
      to…", or "an insurer must…". Discard definitions and licensing.
  - document_types: list of ContraSnap document types this act applies to
      (e.g. ["employment"], ["gym", "phone", "lease", "other"]).
      If omitted, derived automatically from category:
        employment → ["employment"]
        insurance  → ["insurance"]
        consumer   → ["gym", "phone", "lease", "other"]
        rental     → ["lease"]
        credit     → ["other"]
        general    → [] (universal — included for all document types)
"""

# ─── Request settings ───────────────────────────────────────
REQUEST_TIMEOUT = 60  # PDFs can be large
REQUEST_DELAY = 2.0
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ─── LLM settings ────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3"  # or "gemma3:12b" for better quality
CHUNK_SIZE = 6000         # chars per LLM chunk (stay within context window)
CHUNK_OVERLAP = 500       # overlap between chunks to avoid splitting sections

# ─── Output ─────────────────────────────────────────────────────
OUTPUT_DIR = "output"
PDF_CACHE_DIR = "pdf_cache"  # downloaded PDFs are cached here

# ─── South Africa ─────────────────────────────────────────────
ZA_ACTS = [
    # Consumer Protection Act — covers gym, phone, lease, and "other" contracts.
    # Section 14: consumer's right to cooling-off / return of goods.
    # Sections 48-52: unfair, unreasonable or unjust contract terms and
    #   unconscionable conduct — the core "unfair terms" provisions.
    # Sections 55-56: fixed-term agreements — right to cancel with 20
    #   business days' notice, and prohibition on penalty fees beyond
    #   reasonable costs.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act68of2008.pdf",
        "name": "Consumer Protection Act 68 of 2008",
        "short_name": "CPA",
        "act_number": "68 of 2008",
        "category": "consumer",
        "effective_date": "2011-04-01",
        "description": (
            "Promotes a fair, accessible and sustainable marketplace for consumers. "
            "Establishes rights including protection against unfair contract terms, "
            "the right to cancel fixed-term agreements with 20 business days' notice, "
            "and cooling-off rights."
        ),
        "target_sections": ["14", "48", "49", "50", "52", "55", "56"],
    },
    # Labour Relations Act — covers employment contracts.
    # NOT sections 1-2 (purpose / definitions — useless for grounding).
    # Section 64: right to strike.
    # Section 185: right not to be unfairly dismissed.
    # Section 186: meaning of dismissal and unfair labour practice.
    # Section 187: automatically unfair dismissals (e.g. union membership,
    #   pregnancy, whistleblowing).
    # Section 188: other unfair dismissals (fair reason + fair procedure).
    # Section 192: onus of proof in dismissal disputes.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act66of1995.pdf",
        "name": "Labour Relations Act 66 of 1995",
        "short_name": "LRA",
        "act_number": "66 of 1995",
        "category": "employment",
        "effective_date": "1996-11-11",
        "description": (
            "Regulates collective bargaining and the employment relationship. "
            "Provides the right not to be unfairly dismissed, defines automatically "
            "unfair dismissals, and establishes the right to strike."
        ),
        "target_sections": ["64", "185", "186", "187", "188", "192"],
    },
    # Basic Conditions of Employment Act — covers employment contracts.
    # Section 9: ordinary hours of work (max 45 hrs/week, 9 hrs/day).
    # Section 10: overtime (max 10 hrs/week, must be paid at 1.5×).
    # Section 20: annual leave (minimum 21 consecutive days per cycle).
    # Section 22: sick leave entitlements.
    # Section 34: prohibited deductions from pay.
    # Section 37: notice periods for termination by either party.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act75of1997.pdf",
        "name": "Basic Conditions of Employment Act 75 of 1997",
        "short_name": "BCEA",
        "act_number": "75 of 1997",
        "category": "employment",
        "effective_date": "1998-12-01",
        "description": (
            "Sets minimum employment conditions. Limits ordinary hours to 45 per week, "
            "requires overtime to be paid at 1.5×, mandates a minimum of 21 consecutive "
            "days annual leave, and establishes minimum notice periods for termination."
        ),
        "target_sections": ["9", "10", "20", "22", "34", "37"],
    },
    # FAIS Act — covers insurance contracts.
    # Replaces Insurance Act 18/2017 which is a prudential (insurer solvency)
    # act with no policyholder rights useful for grounding.
    # Section 7: general duties of authorised FSPs — must act honestly,
    #   fairly, with due skill and care, and in the client's best interests.
    # Section 8: specific disclosure obligations before any financial
    #   product or service is sold.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act37of2002.pdf",
        "name": "Financial Advisory and Intermediary Services Act 37 of 2002",
        "short_name": "FAIS",
        "act_number": "37 of 2002",
        "category": "insurance",
        "effective_date": "2004-09-30",
        "description": (
            "Regulates financial advisors and intermediaries. Requires providers to act "
            "honestly, fairly and in clients' best interests (section 7), and imposes "
            "pre-sale disclosure obligations on all financial product sales (section 8)."
        ),
        "target_sections": ["7", "8"],
    },
    # Short-term Insurance Act — covers insurance contracts.
    # Section 43: general policyholder protection provisions.
    # Section 44: requirements for the content of short-term policy contracts.
    # Section 53: prohibited acts by insurers (unfair/deceptive practices).
    # Section 54: duties of intermediaries toward policyholders.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act53of1998.pdf",
        "name": "Short-term Insurance Act 53 of 1998",
        "short_name": "STIA",
        "act_number": "53 of 1998",
        "category": "insurance",
        "effective_date": "1998-09-01",
        "description": (
            "Regulates short-term insurance in South Africa. Includes policyholder "
            "protections against unfair insurer practices, requirements for policy "
            "document content, and duties of intermediaries toward policyholders."
        ),
        "target_sections": ["43", "44", "53", "54"],
    },
]

# ─── United Kingdom ───────────────────────────────────────────────
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

# ─── Australia ───────────────────────────────────────────────────────
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

# ─── India ────────────────────────────────────────────────────────────
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
]

# ─── Registry ────────────────────────────────────────────────────────
COUNTRY_CONFIGS = {
    "ZA": ZA_ACTS,
    "GB": GB_ACTS,
    "US": US_ACTS,
    "AU": AU_ACTS,
    "IN": IN_ACTS,
}
