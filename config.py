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


# ───────────────────────────────────────────────────────────
# SOUTH AFRICA
# ───────────────────────────────────────────────────────────
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


# ───────────────────────────────────────────────────────────
# UNITED KINGDOM
# ───────────────────────────────────────────────────────────
GB_ACTS = [
    # Consumer Rights Act 2015 — covers gym, phone, lease, and "other" contracts.
    # Section 31: trader cannot exclude or restrict statutory rights for goods.
    # Section 57: trader cannot exclude or restrict statutory rights for services.
    # Section 62: requirement for contract terms to be fair.
    # Section 63: meaning of unfair term (the main unfair-terms test).
    # Section 68: requirement for contract terms to be transparent.
    # Section 72: contracts that are always unfair (blacklist).
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/2015/15/data.pdf",
        "name": "Consumer Rights Act 2015",
        "short_name": "CRA",
        "act_number": "2015 c. 15",
        "category": "consumer",
        "effective_date": "2015-10-01",
        "description": (
            "Consolidates consumer rights for goods, services and digital content. "
            "Requires contract terms to be fair and transparent, prohibits terms that "
            "create a significant imbalance in the parties' rights and obligations, and "
            "prevents traders from excluding statutory consumer rights."
        ),
        "target_sections": ["31", "57", "62", "63", "68", "72"],
    },
    # Employment Rights Act 1996 — covers employment contracts.
    # Section 86: minimum notice periods for termination by either party.
    # Section 94: right not to be unfairly dismissed.
    # Section 95: circumstances in which an employee is dismissed.
    # Section 98: general test for fairness of dismissal.
    # Section 99: dismissal for family leave reasons is automatically unfair.
    # Section 100: dismissal for health and safety reasons is automatically unfair.
    # Section 103A: dismissal for protected disclosure (whistleblowing) is
    #   automatically unfair.
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1996/18/data.pdf",
        "name": "Employment Rights Act 1996",
        "short_name": "ERA",
        "act_number": "1996 c. 18",
        "category": "employment",
        "effective_date": "1996-08-22",
        "description": (
            "Consolidates fundamental employment rights in Great Britain. Provides the "
            "right not to be unfairly dismissed, minimum notice periods, and automatic "
            "unfair dismissal protection for whistleblowers, health & safety concerns, "
            "and family leave."
        ),
        "target_sections": ["86", "94", "95", "98", "99", "100", "103A"],
    },
    # National Minimum Wage Act 1998 — covers employment contracts.
    # Section 1: workers are entitled to be paid at least the national
    #   minimum wage — any contract term purporting to reduce pay below
    #   NMW is unenforceable.
    # Section 17: underpayment liability — employer must make up the
    #   shortfall plus a penalty.
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/1998/39/data.pdf",
        "name": "National Minimum Wage Act 1998",
        "short_name": "NMWA",
        "act_number": "1998 c. 39",
        "category": "employment",
        "effective_date": "1999-04-01",
        "description": (
            "Establishes the right for workers to be paid at least the national minimum "
            "wage. Any contractual term that purports to pay below NMW is void and "
            "unenforceable."
        ),
        "target_sections": ["1", "17"],
    },
    # Insurance Act 2015 — covers insurance contracts.
    # Section 3: insured's duty of fair presentation before a contract is made.
    # Section 8: insurer's remedies for breach of the fair presentation duty.
    # Section 11: warranty must be exactly complied with; breach suspends
    #   cover but does not end the policy (reform of old law).
    # Section 14: contracting out restrictions — insurer cannot make the
    #   policy less favourable to the insured than the Act provides.
    {
        "source": "url",
        "url": "https://www.legislation.gov.uk/ukpga/2015/4/data.pdf",
        "name": "Insurance Act 2015",
        "short_name": "IA2015",
        "act_number": "2015 c. 4",
        "category": "insurance",
        "effective_date": "2016-08-12",
        "description": (
            "Reforms insurance contract law in the UK. Establishes the duty of fair "
            "presentation, limits the effect of warranties to suspending rather than "
            "voiding cover, and prevents insurers from contracting out of the Act's "
            "consumer protections."
        ),
        "target_sections": ["3", "8", "11", "14"],
    },
]


# ───────────────────────────────────────────────────────────
# UNITED STATES
# Note: US insurance regulation is primarily state-level. There is no
# single federal act that establishes policyholder rights comparable to
# the ZA Short-term Insurance Act or UK Insurance Act 2015. Insurance
# contract grounding for US users should be added per-state as needed.
# ───────────────────────────────────────────────────────────
US_ACTS = [
    # Fair Labor Standards Act 1938 — covers employment contracts.
    # Section 206: minimum wage — every employer must pay at least the
    #   federal minimum wage; any contract clause paying less is void.
    # Section 207: maximum hours — overtime (>40 hrs/week) must be paid
    #   at 1.5× the regular rate.
    # Section 215: prohibited acts — employer may not retaliate against
    #   an employee for exercising FLSA rights.
    {
        "source": "url",
        "url": "https://www.dol.gov/sites/dolgov/files/WHD/legacy/files/FairLaborStandAct.pdf",
        "name": "Fair Labor Standards Act of 1938",
        "short_name": "FLSA",
        "act_number": "Pub.L. 75-718",
        "category": "employment",
        "effective_date": "1938-10-24",
        "description": (
            "Sets federal minimum wage and overtime standards. Employers must pay at "
            "least the federal minimum wage and 1.5× for hours over 40 per week; any "
            "contract term purporting to waive these rights is unenforceable."
        ),
        "target_sections": ["206", "207", "215"],
    },
    # Civil Rights Act 1964 Title VII — covers employment contracts.
    # Section 703: unlawful employment practices — prohibits discrimination
    #   in hiring, firing, pay or terms of employment on the basis of race,
    #   color, religion, sex or national origin.
    # Section 704: retaliation — prohibits adverse action against employees
    #   who oppose discriminatory practices or participate in proceedings.
    {
        "source": "url",
        "url": "https://www.eeoc.gov/sites/default/files/migrated_files/laws/vii.pdf",
        "name": "Civil Rights Act of 1964 Title VII",
        "short_name": "CRA64",
        "act_number": "Pub.L. 88-352",
        "category": "employment",
        "effective_date": "1965-07-02",
        "description": (
            "Prohibits employment discrimination on the basis of race, color, religion, "
            "sex or national origin. Any contract clause that waives these rights or "
            "authorises discriminatory treatment is void and unenforceable."
        ),
        "target_sections": ["703", "704"],
    },
    # FTC Act — covers consumer contracts (gym, phone, lease, other).
    # Section 5: unfair or deceptive acts or practices in or affecting
    #   commerce are unlawful — the foundational US consumer protection
    #   provision. Contract terms that are deceptive or create a
    #   significant imbalance to the consumer's detriment can be
    #   challenged under this section.
    {
        "source": "url",
        "url": "https://www.ftc.gov/sites/default/files/documents/statutes/federal-trade-commission-act/ftc_act_incorporatingus_safe_web_act.pdf",
        "name": "Federal Trade Commission Act",
        "short_name": "FTCA",
        "act_number": "Pub.L. 63-311",
        "category": "consumer",
        "effective_date": "1914-09-26",
        "description": (
            "Prohibits unfair or deceptive acts or practices in commerce. Section 5 is "
            "the primary federal consumer protection provision used to challenge "
            "deceptive contract terms and unfair business practices."
        ),
        "target_sections": ["5"],
    },
]


# ───────────────────────────────────────────────────────────
# AUSTRALIA
# ───────────────────────────────────────────────────────────
AU_ACTS = [
    # Competition and Consumer Act 2010 (Schedule 2 = Australian Consumer Law)
    # — covers gym, phone, lease, and "other" contracts.
    # The ACL sections below live in Schedule 2 of the CCA but keep their
    # own numbering (s.18, s.23 …).
    # Section 18: misleading or deceptive conduct — prohibited absolutely.
    # Section 23: unfair terms in consumer contracts are void.
    # Section 24: meaning of "unfair" (significant imbalance, not reasonably
    #   necessary, would cause detriment).
    # Section 25: examples of terms that may be unfair (non-exhaustive).
    # Section 54: consumer guarantee — goods must be of acceptable quality.
    # Section 60: consumer guarantee — services must be rendered with due
    #   care and skill.
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2010A00116/latest/download",
        "name": "Competition and Consumer Act 2010 (Australian Consumer Law)",
        "short_name": "ACL",
        "act_number": "No. 116 of 2010",
        "category": "consumer",
        "effective_date": "2011-01-01",
        "description": (
            "Schedule 2 (the Australian Consumer Law) prohibits misleading and deceptive "
            "conduct, voids unfair terms in consumer contracts, and establishes consumer "
            "guarantees for goods and services that cannot be excluded by contract."
        ),
        "target_sections": ["18", "23", "24", "25", "54", "60"],
    },
    # Fair Work Act 2009 — covers employment contracts.
    # Section 62: maximum weekly hours (38 ordinary hours + reasonable
    #   additional hours; employer cannot require more).
    # Section 65: right to request flexible working arrangements.
    # Section 385: employee has been unfairly dismissed if the dismissal
    #   was harsh, unjust or unreasonable.
    # Section 386: meaning of dismissed.
    # Section 387: criteria for deciding whether a dismissal is harsh,
    #   unjust or unreasonable (the fairness checklist).
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2009A00028/latest/download",
        "name": "Fair Work Act 2009",
        "short_name": "FWA",
        "act_number": "No. 28 of 2009",
        "category": "employment",
        "effective_date": "2009-07-01",
        "description": (
            "Establishes the national employment relations system. Limits ordinary hours "
            "to 38 per week, protects employees from unfair dismissal, and establishes "
            "the right to request flexible working arrangements."
        ),
        "target_sections": ["62", "65", "385", "386", "387"],
    },
    # Insurance Contracts Act 1984 — covers insurance contracts.
    # Section 13: duty of utmost good faith — each party must act with the
    #   utmost good faith toward the other; breach by the insurer may
    #   entitle the insured to avoid the policy.
    # Section 14: insurer cannot rely on a provision of the contract if to
    #   do so would be to fail to act with utmost good faith.
    # Section 54: insurer cannot refuse to pay a claim solely because the
    #   insured or third party did (or failed to do) something after the
    #   insurance contract was entered into, unless the insurer is
    #   prejudiced by that act or omission.
    {
        "source": "url",
        "url": "https://www.legislation.gov.au/C2004A02611/latest/download",
        "name": "Insurance Contracts Act 1984",
        "short_name": "ICA",
        "act_number": "No. 80 of 1984",
        "category": "insurance",
        "effective_date": "1986-01-01",
        "description": (
            "Governs insurance contracts in Australia. Imposes a duty of utmost good "
            "faith on both parties, prevents insurers from refusing valid claims on "
            "technical post-contract grounds, and limits the effect of exclusion clauses."
        ),
        "target_sections": ["13", "14", "54"],
    },
]


# ───────────────────────────────────────────────────────────
# INDIA
# ───────────────────────────────────────────────────────────
IN_ACTS = [
    # Consumer Protection Act 2019 — covers gym, phone, lease, and "other"
    # contracts. Modernised successor to COPRA 1986.
    # Section 2(47): definition of "unfair contract" — any term that
    #   causes significant change in the rights of the consumer.
    # Section 49: the State Commission may declare an unfair contract term
    #   to be null and void.
    # Section 84: product liability of manufacturer for defective goods.
    # Section 86: product liability of seller.
    {
        "source": "url",
        "url": "https://consumeraffairs.nic.in/sites/default/files/CP%20Act%202019.pdf",
        "name": "Consumer Protection Act 2019",
        "short_name": "CPA2019",
        "act_number": "35 of 2019",
        "category": "consumer",
        "effective_date": "2020-07-20",
        "description": (
            "Modernises consumer protection in India. Defines unfair contracts, empowers "
            "consumer commissions to void unfair terms, establishes product liability for "
            "manufacturers and sellers, and creates a Central Consumer Protection Authority."
        ),
        "target_sections": ["2", "49", "84", "86"],
    },
    # Industrial Disputes Act 1947 — covers employment contracts.
    # Section 25F: conditions precedent to retrenchment — employer must
    #   give one month's notice (or pay in lieu) and pay retrenchment
    #   compensation of 15 days' average pay per completed year of service.
    # Section 25G: procedure for retrenchment — last-in-first-out rule;
    #   employer must give preference to retrenched workers on re-hiring.
    # Section 25H: re-employment of retrenched workers — employer must
    #   offer retrenchment workers preference on re-hiring.
    {
        "source": "url",
        "url": "https://labour.gov.in/sites/default/files/TheIndustrialDisputesAct1947.pdf",
        "name": "Industrial Disputes Act 1947",
        "short_name": "IDA",
        "act_number": "14 of 1947",
        "category": "employment",
        "effective_date": "1947-04-01",
        "description": (
            "Governs industrial disputes and retrenchment in India. Requires employers "
            "to give notice and pay statutory compensation before retrenching workers, "
            "and establishes last-in-first-out retrenchment rules."
        ),
        "target_sections": ["25F", "25G", "25H"],
    },
    # Insurance Act 1938 — covers insurance contracts.
    # Section 45: policy cannot be called into question (repudiated) on
    #   grounds of misstatement or suppression of facts after three years
    #   from the date of issue — the insurer loses the right to void.
    # Section 47: insurer must pay the money to the person entitled;
    #   payment to an unauthorised party does not discharge the insurer.
    # Section 64VB: no risk may be assumed by the insurer unless the
    #   premium has been received — prevents post-dated or credit-based
    #   coverage gaps from being used to deny claims.
    {
        "source": "url",
        "url": "https://irdai.gov.in/documents/37343/3096226/Insurance_Act_1938.pdf",
        "name": "Insurance Act 1938",
        "short_name": "IA1938",
        "act_number": "4 of 1938",
        "category": "insurance",
        "effective_date": "1938-03-26",
        "last_amended": "2021-01-01",
        "description": (
            "The foundational insurance regulation Act in India. Prevents insurers from "
            "repudiating policies on technical grounds after three years, establishes "
            "claim payment obligations, and prohibits coverage gaps from premium timing."
        ),
        "target_sections": ["45", "47", "64VB"],
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
