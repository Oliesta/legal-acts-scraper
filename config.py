"""
Scraper configuration.

Minimum required per entry:
  - source: "url" (download PDF) or "file" (local path)
  - url or path: the PDF location
  - short_name: short identifier for the act (e.g. "IA", "CPA")
  - category: employment | insurance | consumer | rental | credit | general

Optional:
  - target_sections: list of section numbers to keep after LLM extraction.
      The scraper extracts ALL sections first, then discards any whose
      number is not in this list. Only rights-granting sections should be
      kept — those that say "no person may", "every employee is entitled
      to", or "an insurer must". Definitions and licensing sections are
      useless for AI contract grounding and inflate token budgets.
  - act_number, effective_date, description → auto-extracted by LLM if omitted
"""

# ─── Request settings ───────────────────────────────────────
REQUEST_TIMEOUT = 60
REQUEST_DELAY = 2.0
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ─── LLM settings (Ollama — local) ─────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma4:e4b"
CHUNK_SIZE = 8000
CHUNK_OVERLAP = 300

# ─── LLM settings (Groq — cloud, free tier) ─────────────────────────
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GROQ_CHUNK_SIZE = 6000

# ─── LLM settings (Gemini — cloud, free tier: 1M TPM) ──────────────────
# Set GEMINI_API_KEY env var. Get a free key at https://aistudio.google.com/apikey
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash-lite"
GEMINI_CHUNK_SIZE = 100000  # 100k chars ≈ 81k tokens

# ─── Output ─────────────────────────────────────────────────────
OUTPUT_DIR = "output"
PDF_CACHE_DIR = "pdf_cache"


# ───────────────────────────────────────────────────────────
# SOUTH AFRICA
# ───────────────────────────────────────────────────────────
ZA_ACTS = [
    # ── Insurance ────────────────────────────────────────────
    # NOTE: Insurance Act 18/2017 was previously uploaded but is the WRONG
    # act for grounding — it is a prudential (insurer solvency) act with no
    # policyholder rights. It has been removed. Use FAIS + STIA + LTIA instead.
    # In Firestore, set isActive: false on the existing IA 18/2017 document.
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act37of2002.pdf",
        "short_name": "FAIS",
        "act_number": "37 of 2002",
        "category": "insurance",
        "effective_date": "2004-09-30",
        # Section 7: general duties — must act honestly, fairly, in client’s best interests.
        # Section 8: pre-sale disclosure obligations.
        "target_sections": ["7", "8"],
    },
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a53-98.pdf",
        "short_name": "STIA",
        "act_number": "53 of 1998",
        "category": "insurance",
        "effective_date": "1999-01-01",
        # Section 43: general policyholder protection.
        # Section 44: requirements for policy contract content.
        # Section 53: prohibited acts by insurers.
        # Section 54: duties of intermediaries toward policyholders.
        "target_sections": ["43", "44", "53", "54"],
    },
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a52-98.pdf",
        "short_name": "LTIA",
        "act_number": "52 of 1998",
        "category": "insurance",
        "effective_date": "1999-01-01",
        # Section 52: policy benefits — what must be paid.
        # Section 53: reduction of policy benefits.
        # Section 54: paid-up values and surrender values.
        # Section 59: cession and assignment restrictions.
        "target_sections": ["52", "53", "54", "59"],
    },
    # ── Consumer ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/32186_467.pdf",
        "short_name": "CPA",
        "act_number": "68 of 2008",
        "category": "consumer",
        "effective_date": "2011-03-31",
        # Section 14: right to cooling-off / return of goods.
        # Sections 48-52: unfair, unreasonable or unjust contract terms.
        # Sections 55-56: fixed-term agreements — right to cancel with 20
        #   business days’ notice; prohibition on excessive penalty fees.
        "target_sections": ["14", "48", "49", "50", "52", "55", "56"],
    },
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/3706726-11act4of2013protectionofpersonalinforcorrect.pdf",
        "short_name": "POPIA",
        "act_number": "4 of 2013",
        "category": "consumer",
        "effective_date": "2020-07-01",
        # Section 11: lawful processing — consent / legitimate purpose required.
        # Section 18: notification to data subject.
        # Section 69: direct marketing opt-out right.
        "target_sections": ["11", "18", "69"],
    },
    # ── Employment ──────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/act66-1995labourrelations.pdf",
        "short_name": "LRA",
        "act_number": "66 of 1995",
        "category": "employment",
        "effective_date": "1996-11-11",
        # NOT sections 1-2 (purpose/definitions — useless for AI grounding).
        # Section 64: right to strike.
        # Section 185: right not to be unfairly dismissed.
        # Section 186: meaning of dismissal and unfair labour practice.
        # Section 187: automatically unfair dismissals.
        # Section 188: other unfair dismissals (fair reason + fair procedure).
        # Section 192: onus of proof in unfair dismissal disputes.
        "target_sections": ["64", "185", "186", "187", "188", "192"],
    },
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a75-97.pdf",
        "short_name": "BCEA",
        "act_number": "75 of 1997",
        "category": "employment",
        "effective_date": "1998-12-01",
        # Section 9: max 45 ordinary hours/week.
        # Section 10: overtime — max 10 hrs/week, must be paid at 1.5×.
        # Section 20: annual leave — minimum 21 consecutive days.
        # Section 22: sick leave entitlements.
        # Section 34: prohibited deductions from pay.
        # Section 37: minimum notice periods for termination.
        "target_sections": ["9", "10", "20", "22", "34", "37"],
    },
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a55-98ocr.pdf",
        "short_name": "EEA",
        "act_number": "55 of 1998",
        "category": "employment",
        "effective_date": "1999-08-09",
        # Section 6: prohibition of unfair discrimination in employment.
        # Section 11: burden of proof in discrimination disputes.
        "target_sections": ["6", "11"],
    },
    # ── Credit ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.justice.gov.za/mc/vnbp/act2005-034.pdf",
        "short_name": "NCA",
        "act_number": "34 of 2005",
        "category": "credit",
        "effective_date": "2006-06-01",
        # Section 90: unlawful provisions in credit agreements.
        # Section 91: provisions that are void in credit agreements.
        # Section 100: prohibition of certain fees and charges.
        "target_sections": ["90", "91", "100"],
    },
    # ── Rental ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a50-99.pdf",
        "short_name": "RHA",
        "act_number": "50 of 1999",
        "category": "rental",
        "effective_date": "2000-08-01",
        # Section 4: rights and obligations of landlords and tenants.
        # Section 5: unfair practices prohibited.
        "target_sections": ["4", "5"],
    },
]


# ───────────────────────────────────────────────────────────
# UNITED KINGDOM
# ───────────────────────────────────────────────────────────
GB_ACTS = [
    # ── Insurance ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/2015/4/pdfs/ukpga_20150004_en.pdf",
        "short_name": "IA2015",
        "act_number": "2015 c.4",
        "category": "insurance",
        "effective_date": "2016-08-12",
        # Section 3: insured’s duty of fair presentation.
        # Section 8: insurer’s remedies for breach of fair presentation duty.
        # Section 11: warranties — breach suspends cover, does not end policy.
        # Section 14: contracting out — insurer cannot make policy less
        #   favourable than the Act provides.
        "target_sections": ["3", "8", "11", "14"],
    },
    # ── Consumer ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/2015/15/pdfs/ukpga_20150015_en.pdf",
        "short_name": "CRA",
        "act_number": "2015 c.15",
        "category": "consumer",
        "effective_date": "2015-10-01",
        # Section 31: trader cannot exclude statutory rights for goods.
        # Section 57: trader cannot exclude statutory rights for services.
        # Section 62: contract terms must be fair.
        # Section 63: meaning of unfair term.
        # Section 68: terms must be transparent.
        # Section 72: terms that are always unfair (blacklist).
        "target_sections": ["31", "57", "62", "63", "68", "72"],
    },
    # ── Employment ──────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1996/18/pdfs/ukpga_19960018_en.pdf",
        "short_name": "ERA",
        "act_number": "1996 c.18",
        "category": "employment",
        "effective_date": "1996-08-22",
        # Section 86: minimum notice periods.
        # Section 94: right not to be unfairly dismissed.
        # Section 95: circumstances in which employee is dismissed.
        # Section 98: general fairness test for dismissal.
        # Section 99: dismissal for family leave — automatically unfair.
        # Section 100: dismissal for health & safety — automatically unfair.
        # Section 103A: dismissal for whistleblowing — automatically unfair.
        "target_sections": ["86", "94", "95", "98", "99", "100", "103A"],
    },
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1998/39/pdfs/ukpga_19980039_en.pdf",
        "short_name": "NMWA",
        "act_number": "1998 c.39",
        "category": "employment",
        "effective_date": "1999-04-01",
        # Section 1: entitlement to NMW — any contractual term paying below
        #   NMW is void and unenforceable.
        # Section 17: underpayment liability.
        "target_sections": ["1", "17"],
    },
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/2010/15/pdfs/ukpga_20100015_en.pdf",
        "short_name": "EA",
        "act_number": "2010 c.15",
        "category": "employment",
        "effective_date": "2010-10-01",
        # Section 39: discrimination in employment — prohibited.
        # Section 40: harassment in employment — prohibited.
        # Section 60: prohibited pre-employment health enquiries.
        "target_sections": ["39", "40", "60"],
    },
    # ── Rental ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1988/50/pdfs/ukpga_19880050_en.pdf",
        "short_name": "HA",
        "act_number": "1988 c.50",
        "category": "rental",
        "effective_date": "1989-01-15",
        # Section 1: assured tenancy — right to remain.
        # Section 21: no-fault eviction procedure (notice requirements).
        "target_sections": ["1", "21"],
    },
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1985/70/pdfs/ukpga_19850070_en.pdf",
        "short_name": "LTA",
        "act_number": "1985 c.70",
        "category": "rental",
        "effective_date": "1985-10-30",
        # Section 11: landlord’s repairing obligations (structure, exterior,
        #   installations).
        # Section 17: no contracting out of s.11 obligations.
        "target_sections": ["11", "17"],
    },
]


# ───────────────────────────────────────────────────────────
# UNITED STATES
# Note: US insurance regulation is primarily state-level. There is no
# single federal act that establishes policyholder rights comparable to
# the ZA or UK acts. Add state-specific acts per-deployment as needed.
# ───────────────────────────────────────────────────────────
US_ACTS = [
    # ── Consumer ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/STATUTE-38/pdf/STATUTE-38-Pg717.pdf",
        "short_name": "FTCA",
        "act_number": "Pub.L. 63-311",
        "category": "consumer",
        "effective_date": "1914-09-26",
        # Section 5: unfair or deceptive acts or practices — the foundational
        #   US consumer protection provision.
        "target_sections": ["5"],
    },
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/PLAW-111publ203/pdf/PLAW-111publ203.pdf",
        "short_name": "CFPA",
        "act_number": "Pub.L. 111-203",
        "category": "consumer",
        "effective_date": "2010-07-21",
        # Section 1031: prohibition on unfair, deceptive, or abusive acts.
        # Section 1036: unfair, deceptive, or abusive acts unlawful.
        "target_sections": ["1031", "1036"],
    },
    # ── Employment ──────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/COMPS-1514/pdf/COMPS-1514.pdf",
        "short_name": "FLSA",
        "act_number": "Pub.L. 75-718",
        "category": "employment",
        "effective_date": "1938-10-24",
        # Section 206: minimum wage — any contract paying less is void.
        # Section 207: overtime — must be paid at 1.5× for hours over 40/week.
        # Section 215: prohibited acts — no retaliation for exercising FLSA rights.
        "target_sections": ["206", "207", "215"],
    },
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/STATUTE-78/pdf/STATUTE-78-Pg241.pdf",
        "short_name": "CRA64",
        "act_number": "Pub.L. 88-352",
        "category": "employment",
        "effective_date": "1965-07-02",
        # Section 703: unlawful employment discrimination (race, colour,
        #   religion, sex, national origin).
        # Section 704: retaliation prohibited.
        "target_sections": ["703", "704"],
    },
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/STATUTE-104/pdf/STATUTE-104-Pg327.pdf",
        "short_name": "ADA",
        "act_number": "Pub.L. 101-336",
        "category": "employment",
        "effective_date": "1990-07-26",
        # Section 12112: disability discrimination in employment prohibited.
        "target_sections": ["12112"],
    },
    # ── Credit ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.govinfo.gov/content/pkg/STATUTE-82/pdf/STATUTE-82-Pg146.pdf",
        "short_name": "TILA",
        "act_number": "Pub.L. 90-321",
        "category": "credit",
        "effective_date": "1968-05-29",
        # Section 128: required disclosures in closed-end credit contracts.
        # Section 130: civil liability for failure to disclose.
        "target_sections": ["128", "130"],
    },
]


# ───────────────────────────────────────────────────────────
# AUSTRALIA
# ───────────────────────────────────────────────────────────
AU_ACTS = [
    # ── Insurance ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2004A02944/latest/downloads",
        "short_name": "ICA",
        "act_number": "No. 80 of 1984",
        "category": "insurance",
        "effective_date": "1986-01-01",
        # Section 13: duty of utmost good faith — both parties.
        # Section 14: insurer cannot rely on a provision if doing so would
        #   breach utmost good faith.
        # Section 54: insurer cannot refuse a claim solely because of an
        #   act/omission by the insured after the contract was entered into,
        #   unless the insurer is prejudiced.
        "target_sections": ["13", "14", "54"],
    },
    # ── Consumer ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2004A00109/latest/downloads",
        "short_name": "CCA",
        "act_number": "No. 51 of 1974",
        "category": "consumer",
        "effective_date": "2011-01-01",
        # Australian Consumer Law lives in Schedule 2 of the CCA.
        # Section 18: misleading or deceptive conduct — prohibited.
        # Section 23: unfair terms in consumer contracts are void.
        # Section 24: meaning of “unfair” (significant imbalance test).
        # Section 25: examples of terms that may be unfair.
        # Section 54: goods must be of acceptable quality.
        # Section 60: services must be rendered with due care and skill.
        "target_sections": ["18", "23", "24", "25", "54", "60"],
    },
    # ── Employment ──────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2009A00028/latest/downloads",
        "short_name": "FWA",
        "act_number": "No. 28 of 2009",
        "category": "employment",
        "effective_date": "2009-07-01",
        # Section 62: maximum weekly hours (38 ordinary + reasonable additional).
        # Section 65: right to request flexible working arrangements.
        # Section 385: protected from unfair dismissal if harsh/unjust/unreasonable.
        # Section 386: meaning of dismissed.
        # Section 387: criteria for deciding unfair dismissal.
        "target_sections": ["62", "65", "385", "386", "387"],
    },
    # ── Credit ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2009A00134/latest/downloads",
        "short_name": "NCCP",
        "act_number": "No. 134 of 2009",
        "category": "credit",
        "effective_date": "2010-07-01",
        # Section 47: licensee must not engage in credit activities dishonestly.
        # Section 131: consumer credit contract must be in writing.
        "target_sections": ["47", "131"],
    },
]


# ───────────────────────────────────────────────────────────
# INDIA
# ───────────────────────────────────────────────────────────
IN_ACTS = [
    # ── Insurance ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.indiacode.nic.in/bitstream/123456789/2304/1/a1938-04.pdf",
        "short_name": "IA1938",
        "act_number": "4 of 1938",
        "category": "insurance",
        "effective_date": "1938-03-26",
        # Section 45: policy cannot be repudiated after 3 years on grounds
        #   of misstatement or suppression.
        # Section 47: insurer must pay the entitled person; unauthorised
        #   payment does not discharge the insurer.
        # Section 64VB: no risk assumed unless premium received.
        "target_sections": ["45", "47", "64VB"],
    },
    # ── Consumer ────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.indiacode.nic.in/bitstream/123456789/15256/1/eng201935.pdf",
        "short_name": "CPA2019",
        "act_number": "35 of 2019",
        "category": "consumer",
        "effective_date": "2020-07-20",
        # Section 2(47): definition of unfair contract.
        # Section 49: commission may declare unfair term null and void.
        # Section 84: product liability of manufacturer.
        # Section 86: product liability of seller.
        "target_sections": ["49", "84", "86"],
    },
    # ── Employment ──────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.indiacode.nic.in/bitstream/123456789/20352/1/the_industrial_disputes_act.pdf",
        "short_name": "IDA",
        "act_number": "14 of 1947",
        "category": "employment",
        "effective_date": "1947-04-01",
        # Section 25F: conditions before retrenchment — one month notice +
        #   15 days pay per year of service.
        # Section 25G: LIFO retrenchment procedure.
        # Section 25H: preference for retrenched workers on re-hiring.
        "target_sections": ["25F", "25G", "25H"],
    },
    {
        "source": "url",
        "url": "https://www.indiacode.nic.in/bitstream/123456789/20960/1/the_payment_of_wages_act%2c_1936.pdf",
        "short_name": "PWA",
        "act_number": "4 of 1936",
        "category": "employment",
        "effective_date": "1937-03-28",
        # Section 7: deductions from wages — only permitted deductions listed.
        # Section 13: fines — employer may only impose fines as prescribed.
        "target_sections": ["7", "13"],
    },
    # ── Rental ─────────────────────────────────────────────
    {
        "source": "url",
        "url": "https://www.indiacode.nic.in/bitstream/123456789/2158/3/A2016-16.pdf",
        "short_name": "RERA",
        "act_number": "16 of 2016",
        "category": "rental",
        "effective_date": "2016-05-01",
        # Section 11: obligations of promoter — must deliver as promised.
        # Section 18: return of amount on failure to complete.
        "target_sections": ["11", "18"],
    },
]


# ─── Registry ────────────────────────────────────────────────────────
COUNTRY_CONFIGS = {
    "ZA": ZA_ACTS,
    "GB": GB_ACTS,
    "US": US_ACTS,
    "AU": AU_ACTS,
    "IN": IN_ACTS,
}
