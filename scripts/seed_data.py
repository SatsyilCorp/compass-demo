#!/usr/bin/env python3
"""Compass synthetic seed-data generator.

Generates a MOCK ONR S&T grants portfolio and writes it, plus a set of
ingest-pipeline demo fixtures and license records, as plain JSON files under
``seed/``. Everything here is **fully synthetic** — invented program names,
invented fictional performer organizations, invented dollar amounts. No real
CUI/PII, no real people, no real award numbers.

Design notes (adapted from the ``demo-seed-toolkit`` block in
satsyil-blocks/code/py/satsyil_demokit — same spirit of "caller describes the
shape, generator renders it, everything is offline and deterministic", but
grants/portfolio tabular data isn't in that block's surface, so the domain
generator here is purpose-built. This script intentionally has **zero**
third-party dependencies (no faker, no AWS SDK) so it runs anywhere with
Python 3.11+ and nothing to `pip install` — a deliberate deviation from the
block's `faker` dependency, made because tabular demo rows don't need
Faker-quality names, just plausible, clearly-fictional ones).

Output (all under ``seed/``):
  grants_portfolio.json              — ~400 grants, curated-table shape (the
                                        baseline portfolio already "in" Compass)
  drops/drop_good.json               — new incoming batch, canonical field
                                        names, all valid — demos a clean ingest
  drops/drop_compatible_variant.json — same kind of batch, renamed/reshaped
                                        columns a real exporter would use — the
                                        pipeline is expected to normalize this
  drops/drop_incompatible_bad.json   — new batch with missing required fields
                                        and malformed rows — must be quarantined
  licenses.json                      — 8 data-vendor license records
  SYNTHETIC-DATA-MANIFEST.md         — every fixture, counts, and the explicit
                                        "no real CUI/PII" assertion

Run: `python3 scripts/seed_data.py` from anywhere (paths are resolved off
this file's location). Deterministic for a fixed SEED except renewal dates on
licenses, which are intentionally computed relative to "now" so the demo
always looks current when regenerated.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

SEED = 20260810  # fixed -> reproducible output (except license renewal dates)

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = REPO_ROOT / "seed"
DROPS_DIR = SEED_DIR / "drops"

# --------------------------------------------------------------------------- #
# Domain vocabulary
# --------------------------------------------------------------------------- #

PROGRAM_AREAS = [
    "AI/ML", "Autonomy", "Undersea", "Directed Energy",
    "Quantum", "Cyber", "Materials", "Biotech",
]

# Grant-number program code — deliberately NOT the real N00014 ONR contract
# format, so nothing here can be mistaken for an actual award identifier.
PROGRAM_CODE = {
    "AI/ML": "AIML", "Autonomy": "AUTO", "Undersea": "USEA",
    "Directed Energy": "DEWX", "Quantum": "QNTM", "Cyber": "CYBR",
    "Materials": "MATL", "Biotech": "BIOT",
}

ORG_UNITS = ["ONR-Corporate", "Code-30", "Code-31", "Code-32", "Code-34", "Code-35"]
ORG_UNIT_WEIGHTS = [8, 25, 20, 20, 15, 12]  # sums to 100

PROGRAM_AREA_WEIGHTS = {
    "AI/ML": 15, "Autonomy": 14, "Undersea": 12, "Directed Energy": 10,
    "Quantum": 9, "Cyber": 13, "Materials": 14, "Biotech": 13,
}  # sums to 100

# Exact per-fiscal-year counts for the main portfolio (sums to 400; a gentle
# upward trend so year-over-year charts have something to show).
FY_COUNTS = {
    2019: 32, 2020: 36, 2021: 40, 2022: 44,
    2023: 52, 2024: 60, 2025: 68, 2026: 68,
}
assert sum(FY_COUNTS.values()) == 400

ADJECTIVES = [
    "Robust", "Scalable", "Resilient", "Adaptive", "Low-Latency",
    "Next-Generation", "Field-Deployable", "Energy-Efficient",
    "High-Fidelity", "Modular",
]

STOPWORDS = {"a", "an", "the", "for", "to", "in", "of", "and", "via", "under", "toward"}


def title_case(phrase: str) -> str:
    """Title-case a phrase without mangling embedded acronyms (AUV, GPS, ...)."""
    words = phrase.split(" ")
    out = []
    for i, w in enumerate(words):
        core = w.strip("()")
        if core.isupper() and len(core) > 1:
            out.append(w)  # leave acronyms alone
        elif w.lower() in STOPWORDS and i != 0:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:] if w else w)
    return " ".join(out)


PROGRAM_VOCAB: Dict[str, Dict[str, List[str]]] = {
    "AI/ML": {
        "methods": [
            "multi-agent reinforcement learning", "explainable neural inference",
            "federated learning", "transformer-based sequence modeling",
            "Bayesian uncertainty quantification", "self-supervised representation learning",
            "graph neural network reasoning", "human-machine teaming policy optimization",
        ],
        "applications": [
            "intelligence, surveillance, and reconnaissance (ISR) triage",
            "predictive maintenance for shipboard systems",
            "command-and-control decision support",
            "adversarial threat classification",
            "sensor fusion for contested environments",
            "natural-language mission planning",
        ],
        "keywords": ["latency", "model drift", "training-data scarcity", "edge deployment", "trust calibration"],
        "metrics": ["inference latency", "classification accuracy", "false-alarm rate", "operator trust score"],
    },
    "Autonomy": {
        "methods": [
            "swarm coordination algorithms", "distributed task allocation",
            "model-predictive control", "behavior-tree mission planning",
            "onboard perception-to-action pipelines", "cooperative multi-vehicle routing",
        ],
        "applications": [
            "unmanned surface vessel (USV) picket lines",
            "group unmanned aerial system (UAS) reconnaissance",
            "autonomous convoy escort", "contested-environment navigation",
            "GPS-denied waypoint following",
        ],
        "keywords": ["autonomy assurance", "degraded communications", "swarm resilience", "onboard compute limits"],
        "metrics": ["mission completion rate", "swarm coordination overhead", "navigation drift", "time-to-reroute"],
    },
    "Undersea": {
        "methods": [
            "passive acoustic signal processing", "synthetic aperture sonar imaging",
            "low-frequency active sonar waveform design", "hydrodynamic hull-form optimization",
            "autonomous underwater vehicle (AUV) navigation", "undersea acoustic communications",
        ],
        "applications": [
            "submarine detection and tracking", "seabed mapping",
            "undersea cable route surveying", "anti-submarine warfare (ASW) sensor networks",
            "littoral mine-countermeasure operations",
        ],
        "keywords": ["acoustic signature reduction", "ambient ocean noise", "bathymetric uncertainty", "depth-rated housings"],
        "metrics": ["detection range", "signal-to-noise ratio", "localization error", "endurance"],
    },
    "Directed Energy": {
        "methods": [
            "high-energy laser beam control", "adaptive optics wavefront correction",
            "high-power microwave source design", "thermal management for solid-state lasers",
            "pulsed-power system integration",
        ],
        "applications": [
            "counter-unmanned aerial system (C-UAS) engagement",
            "shipboard self-defense layers",
            "directed-energy weapon test-bed evaluation",
            "atmospheric propagation modeling",
        ],
        "keywords": ["beam quality", "thermal blooming", "power density", "duty-cycle limits"],
        "metrics": ["beam quality factor", "time-on-target", "duty cycle", "engagement range"],
    },
    "Quantum": {
        "methods": [
            "quantum key distribution protocol design", "trapped-ion qubit control",
            "quantum-enhanced magnetometry", "quantum error-correction code development",
            "photonic quantum sensing", "quantum-secure communications",
        ],
        "applications": [
            "undersea navigation without GPS", "secure fleet communications",
            "gravimetric anomaly detection", "precision timing for distributed platforms",
        ],
        "keywords": ["decoherence", "qubit fidelity", "entanglement distribution", "cryogenic control electronics"],
        "metrics": ["qubit fidelity", "coherence time", "key generation rate", "sensor sensitivity"],
    },
    "Cyber": {
        "methods": [
            "zero-trust network architecture design", "anomaly-based intrusion detection",
            "supply-chain firmware attestation", "adversarial machine-learning defense",
            "secure software-defined networking",
        ],
        "applications": [
            "shipboard combat-system network hardening", "tactical edge cyber resilience",
            "cross-domain solution assurance",
            "industrial-control-system (ICS) protection for propulsion systems",
        ],
        "keywords": ["attack surface", "lateral movement", "zero-day exposure", "cyber-physical resilience"],
        "metrics": ["mean time to detect", "false-positive rate", "patch latency", "attack-surface reduction"],
    },
    "Materials": {
        "methods": [
            "additive manufacturing process qualification", "corrosion-resistant coating development",
            "composite laminate fatigue characterization", "high-entropy alloy design",
            "self-healing polymer synthesis",
        ],
        "applications": [
            "hull coating for biofouling resistance", "lightweight airframe structures",
            "thermal-protection systems for hypersonic platforms", "battery electrode materials",
        ],
        "keywords": ["fatigue life", "fracture toughness", "corrosion rate", "specific strength"],
        "metrics": ["fatigue life", "corrosion rate", "specific strength", "thermal tolerance"],
    },
    "Biotech": {
        "methods": [
            "synthetic biology pathway engineering", "biomarker-based fatigue detection",
            "field-deployable diagnostic assay development", "human performance physiological modeling",
            "microbiome-based biofouling mitigation",
        ],
        "applications": [
            "warfighter fatigue and readiness monitoring",
            "rapid diagnostic triage in austere environments",
            "biofilm-resistant hull coatings", "cold-chain-free vaccine stabilization",
        ],
        "keywords": ["biomarker specificity", "assay sensitivity", "physiological baseline", "field ruggedization"],
        "metrics": ["assay sensitivity", "diagnostic turnaround time", "biomarker specificity", "shelf stability"],
    },
}

TITLE_PATTERNS = [
    "{method_tc} for {application_tc}",
    "Advancing {method} to Improve {application}",
    "{adj} {method_tc} for {application_tc}",
    "Toward {adj_lower} {method}: Implications for {application}",
    "Phase {phase}: {method_tc} for {application_tc}",
    "{adj} Approaches to {application_tc} via {method_tc}",
]

ABSTRACT_S2_PATTERNS = [
    "The performer will design, implement, and evaluate a prototype capability, "
    "validating performance against {keyword2}-related benchmarks under realistic "
    "operational conditions.",
    "Research activities include algorithm development, {method2} integration, and "
    "iterative field evaluation to quantify gains in {metric}.",
    "The team will conduct a phased study combining {method2} with legacy system "
    "integration to reduce risk prior to a transition decision.",
]

ABSTRACT_S4_PATTERNS = [
    "Key technical risks include {keyword3} and constrained {keyword4}, which will "
    "be tracked via quarterly milestone reviews.",
    "A principal risk to schedule is {keyword3}; the performer will mitigate this "
    "through early prototyping and government checkpoint reviews.",
]

ORG_PREFIXES = [
    "Meridian", "Bluewater", "Highland", "Cascade", "Ironclad", "Northgate",
    "Silverline", "Vantage", "Redshift", "Cobalt", "Summit", "Anchor",
    "Pelican", "Granite", "Foxglove", "Harborlight", "Longview", "Beacon",
    "Sable", "Driftwood", "Wraith", "Halcyon", "Amberfield", "Cinderpoint",
    "Windrose", "Palisade", "Stonebridge", "Farview", "Copperline", "Duskwater",
]
UNIV_SUFFIXES = ["Institute of Technology", "State University", "Polytechnic University", "College of Engineering"]
COMPANY_SUFFIXES = [
    "Systems, Inc.", "Dynamics Corp.", "Applied Research LLC", "Labs",
    "Defense Technologies", "Advanced Systems Group", "Robotics Corp.", "Analytics Inc.",
]


def fictional_org_name(rng: random.Random) -> str:
    """A clearly-invented performer org name — no real university or company."""
    prefix = rng.choice(ORG_PREFIXES)
    if rng.random() < 0.45:
        if rng.random() < 0.4:
            return f"University of {prefix}"
        return f"{prefix} {rng.choice(UNIV_SUFFIXES)}"
    return f"{prefix} {rng.choice(COMPANY_SUFFIXES)}"


def gen_title(rng: random.Random, program_area: str) -> Tuple[str, str, str]:
    vocab = PROGRAM_VOCAB[program_area]
    method = rng.choice(vocab["methods"])
    application = rng.choice(vocab["applications"])
    adj = rng.choice(ADJECTIVES)
    pattern = rng.choice(TITLE_PATTERNS)
    title = pattern.format(
        method=method, method_tc=title_case(method),
        application=application, application_tc=title_case(application),
        adj=adj, adj_lower=adj.lower(),
        phase=rng.choice(["I", "II", "III"]),
    )
    return title, method, application


def gen_abstract(rng: random.Random, program_area: str, method: str, application: str) -> str:
    vocab = PROGRAM_VOCAB[program_area]
    keyword = rng.choice(vocab["keywords"])
    keyword2 = rng.choice([k for k in vocab["keywords"] if k != keyword] or vocab["keywords"])
    method2 = rng.choice([m for m in vocab["methods"] if m != method] or vocab["methods"])
    metric = rng.choice(vocab["metrics"])

    s1 = (f"This effort develops {method} to address persistent {keyword}-driven "
          f"challenges in {application}.")
    s2 = rng.choice(ABSTRACT_S2_PATTERNS).format(keyword2=keyword2, method2=method2, metric=metric)
    s3 = (f"Expected outcomes include a measurable improvement in {metric} and a "
          f"documented transition path informed by operational stakeholder feedback.")
    sentences = [s1, s2, s3]
    if rng.random() < 0.5:
        keyword3 = rng.choice(vocab["keywords"])
        keyword4 = rng.choice([k for k in vocab["keywords"] if k != keyword3] or vocab["keywords"])
        s4 = rng.choice(ABSTRACT_S4_PATTERNS).format(keyword3=keyword3, keyword4=keyword4)
        sentences.append(s4)
    return " ".join(sentences)


AMOUNT_BANDS = [
    (50_000, 250_000, 35),
    (250_000, 1_000_000, 35),
    (1_000_000, 3_000_000, 20),
    (3_000_000, 8_000_000, 10),
]


def gen_amount(rng: random.Random) -> int:
    lo, hi, _ = rng.choices(AMOUNT_BANDS, weights=[b[2] for b in AMOUNT_BANDS])[0]
    val = rng.uniform(lo, hi)
    return int(round(val / 1000.0)) * 1000


def fy_created_at(rng: random.Random, fiscal_year: int) -> str:
    """A plausible curation timestamp within the federal fiscal year (Oct 1 prior
    calendar year through Sep 30 of ``fiscal_year``)."""
    start = dt.date(fiscal_year - 1, 10, 1)
    end = dt.date(fiscal_year, 9, 30)
    span = (end - start).days
    d = start + dt.timedelta(days=rng.randint(0, span))
    t = dt.time(hour=rng.randint(7, 18), minute=rng.randint(0, 59), second=rng.randint(0, 59))
    return dt.datetime.combine(d, t, tzinfo=dt.timezone.utc).isoformat()


class SeqCounter:
    """Global grant_no sequence — guarantees uniqueness across every file this
    script writes in one run (main portfolio + all three drop batches)."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n


def gen_grant(rng: random.Random, seq: SeqCounter, fiscal_year: int,
              batch_id: str, batch_tag: str = "") -> Dict[str, Any]:
    program_area = rng.choices(PROGRAM_AREAS, weights=[PROGRAM_AREA_WEIGHTS[p] for p in PROGRAM_AREAS])[0]
    org_unit = rng.choices(ORG_UNITS, weights=ORG_UNIT_WEIGHTS)[0]
    title, method, application = gen_title(rng, program_area)
    abstract = gen_abstract(rng, program_area, method, application)
    n = seq.next()
    tag = f"{batch_tag}-" if batch_tag else ""
    grant_no = f"ONRD-{fiscal_year}-{PROGRAM_CODE[program_area]}-{tag}{n:05d}"
    classification_band = "Public-Mock" if rng.random() < 0.10 else "CUI-Mock"
    return {
        "grant_no": grant_no,
        "title": title,
        "abstract": abstract,
        "program_area": program_area,
        "fiscal_year": fiscal_year,
        "amount_usd": gen_amount(rng),
        "awardee": fictional_org_name(rng),
        "org_unit": org_unit,
        "classification_band": classification_band,
        "batch_id": batch_id,
        "created_at": fy_created_at(rng, fiscal_year),
    }


# --------------------------------------------------------------------------- #
# Main portfolio (the "good" baseline dataset already curated into Compass)
# --------------------------------------------------------------------------- #

def build_main_portfolio(rng: random.Random, seq: SeqCounter) -> List[Dict[str, Any]]:
    grants: List[Dict[str, Any]] = []
    for fy, count in FY_COUNTS.items():
        for _ in range(count):
            grants.append(gen_grant(rng, seq, fiscal_year=fy, batch_id="seed-initial-2026"))
    return grants


# --------------------------------------------------------------------------- #
# Drop 1: good — canonical field names, all valid
# --------------------------------------------------------------------------- #

def build_drop_good(rng: random.Random, seq: SeqCounter, n: int = 40) -> List[Dict[str, Any]]:
    return [gen_grant(rng, seq, fiscal_year=2026, batch_id="drop-good-2026-08", batch_tag="D1")
            for _ in range(n)]


# --------------------------------------------------------------------------- #
# Drop 2: compatible schema variant — renamed/reshaped columns a real legacy
# exporter would produce. Fully recoverable by the ingest normalizer via a
# straightforward field-rename + light type coercion (currency string, "FYnnnn"
# string fiscal year) — no data is actually missing or wrong.
# --------------------------------------------------------------------------- #

def to_compatible_variant(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "award_id": rec["grant_no"],
        "project_title": rec["title"],
        "summary": rec["abstract"],
        "portfolio_area": rec["program_area"],
        "fy": f"FY{rec['fiscal_year']}",
        "obligated_amount_usd": f"${rec['amount_usd']:,.2f}",
        "performer_org": rec["awardee"],
        "command_code": rec["org_unit"],
        "marking": rec["classification_band"],
        "source_system": "Legacy-GMS-Export",  # extra field the normalizer should just drop
    }


def build_drop_compatible(rng: random.Random, seq: SeqCounter, n: int = 40) -> List[Dict[str, Any]]:
    canonical = [gen_grant(rng, seq, fiscal_year=2026, batch_id="drop-compat-2026-08", batch_tag="D2")
                 for _ in range(n)]
    return [to_compatible_variant(r) for r in canonical]


# --------------------------------------------------------------------------- #
# Drop 3: incompatible/bad — missing required fields + malformed rows that a
# real quality gate must quarantine. Field names match canonical (the defect
# here is bad/missing VALUES, not renamed columns — that scenario is covered
# by drop 2).
# --------------------------------------------------------------------------- #

def _mutate_missing(field: str):
    def fn(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        rec = dict(rec)
        del rec[field]
        return rec, f"required field '{field}' omitted entirely"
    return fn


def _mutate_null(field: str):
    def fn(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        rec = dict(rec)
        rec[field] = None
        return rec, f"required field '{field}' present but null"
    return fn


def _mutate_non_numeric_amount(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["amount_usd"] = "TBD"
    return rec, "amount_usd is the non-numeric string 'TBD'"


def _mutate_negative_amount(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["amount_usd"] = -250000
    return rec, "amount_usd is negative"


def _mutate_amount_wrong_type(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["amount_usd"] = {"value": 500000, "currency": "USD"}
    return rec, "amount_usd is a nested object instead of a number"


def _mutate_non_numeric_fy(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["fiscal_year"] = "FY2026"
    return rec, "fiscal_year is the string 'FY2026' instead of an integer"


def _mutate_fy_out_of_range(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["fiscal_year"] = 1998
    return rec, "fiscal_year (1998) predates any real ONR S&T program in this portfolio"


def _mutate_unknown_org_unit(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["org_unit"] = "Code-99"
    return rec, "org_unit 'Code-99' is not a recognized org unit"


def _mutate_empty_title(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rec = dict(rec)
    rec["title"] = ""
    return rec, "title is an empty string"


def build_drop_incompatible(
    rng: random.Random, seq: SeqCounter, duplicate_target: str, n_clean: int = 45,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    def _mutate_duplicate_grant_no(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        rec = dict(rec)
        rec["grant_no"] = duplicate_target
        return rec, f"grant_no reuses '{duplicate_target}' already used by drop_good.json (uniqueness violation)"

    defect_map = {
        "missing_grant_no": _mutate_missing("grant_no"),
        "missing_title": _mutate_missing("title"),
        "missing_program_area": _mutate_missing("program_area"),
        "missing_fiscal_year": _mutate_missing("fiscal_year"),
        "missing_amount_usd": _mutate_missing("amount_usd"),
        "missing_org_unit": _mutate_missing("org_unit"),
        "null_awardee": _mutate_null("awardee"),
        "non_numeric_amount": _mutate_non_numeric_amount,
        "negative_amount": _mutate_negative_amount,
        "amount_wrong_type": _mutate_amount_wrong_type,
        "non_numeric_fiscal_year": _mutate_non_numeric_fy,
        "fiscal_year_out_of_range": _mutate_fy_out_of_range,
        "unknown_org_unit": _mutate_unknown_org_unit,
        "empty_title": _mutate_empty_title,
        "duplicate_grant_no": _mutate_duplicate_grant_no,
    }

    markers = ["clean"] * n_clean + list(defect_map.keys())
    rng.shuffle(markers)

    records: List[Dict[str, Any]] = []
    defect_log: List[Dict[str, Any]] = []
    for idx, marker in enumerate(markers):
        rec = gen_grant(rng, seq, fiscal_year=2026, batch_id="drop-bad-2026-08", batch_tag="D3")
        if marker == "clean":
            records.append(rec)
            continue
        mutated, note = defect_map[marker](rec)
        records.append(mutated)
        defect_log.append({
            "index": idx,
            "defect": marker,
            "grant_no": mutated.get("grant_no", "<missing>"),
            "note": note,
        })
    return records, defect_log


# --------------------------------------------------------------------------- #
# Licenses
# --------------------------------------------------------------------------- #

VENDOR_CATALOG = [
    {"vendor": "Clarivate Web of Science", "product": "Web of Science Core Collection",
     "datasets": ["Publication & Citation Index", "Grant Abstracts Corpus"]},
    {"vendor": "Dimensions", "product": "Dimensions Analytics",
     "datasets": ["Publication & Citation Index", "Grant Abstracts Corpus"]},
    {"vendor": "Crunchbase", "product": "Crunchbase Pro API",
     "datasets": ["Startup & Company Intelligence Feed"]},
    {"vendor": "Lens.org", "product": "Lens.org Patent & Scholarly Search",
     "datasets": ["Patent Landscape Feed"]},
    {"vendor": "Elsevier", "product": "Scopus & SciVal",
     "datasets": ["Publication & Citation Index"]},
    {"vendor": "PitchBook Data", "product": "PitchBook Platform",
     "datasets": ["Startup & Company Intelligence Feed"]},
    {"vendor": "CB Insights", "product": "CB Insights Platform",
     "datasets": ["Startup & Company Intelligence Feed"]},
    {"vendor": "GovTribe", "product": "GovTribe Federal Intelligence",
     "datasets": ["Federal Contract Intelligence Feed"]},
]

OWNER_TEAMS = [
    "S&T Analytics Program Office", "Portfolio Intelligence Team",
    "Data Curation Office", "BD Market Intelligence Cell",
]


def build_licenses(rng: random.Random) -> List[Dict[str, Any]]:
    today = dt.date.today()
    soon_days = rng.sample(range(10, 46), 3)
    later_days = rng.sample(range(70, 380), len(VENDOR_CATALOG) - 3)
    offsets = soon_days + later_days
    rng.shuffle(offsets)

    licenses = []
    for i, v in enumerate(VENDOR_CATALOG):
        seats_total = rng.randint(10, 60)
        seats_used = rng.randint(int(seats_total * 0.3), seats_total)
        renews_on = (today + dt.timedelta(days=offsets[i])).isoformat()
        licenses.append({
            "id": i + 1,
            "vendor": v["vendor"],
            "product": v["product"],
            "datasets": v["datasets"],
            "entitlements": (
                f"Enterprise site license — full-text/API access "
                f"({rng.choice([2000, 5000, 10000])} calls/day), bibliometric export"
            ),
            "seats_used": seats_used,
            "seats_total": seats_total,
            "renews_on": renews_on,
            "owner": rng.choice(OWNER_TEAMS),
            "status": "active",
        })
    return licenses


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #

def build_manifest(
    portfolio: List[Dict[str, Any]],
    drop_good: List[Dict[str, Any]],
    drop_compat: List[Dict[str, Any]],
    drop_bad: List[Dict[str, Any]],
    defect_log: List[Dict[str, Any]],
    licenses: List[Dict[str, Any]],
    generated_at: str,
) -> str:
    fy_counts = {}
    prog_counts = {}
    org_counts = {}
    for g in portfolio:
        fy_counts[g["fiscal_year"]] = fy_counts.get(g["fiscal_year"], 0) + 1
        prog_counts[g["program_area"]] = prog_counts.get(g["program_area"], 0) + 1
        org_counts[g["org_unit"]] = org_counts.get(g["org_unit"], 0) + 1

    fy_rows = "\n".join(f"| {fy} | {fy_counts[fy]} |" for fy in sorted(fy_counts))
    prog_rows = "\n".join(f"| {p} | {prog_counts[p]} |" for p in PROGRAM_AREAS)
    org_rows = "\n".join(f"| {o} | {org_counts.get(o, 0)} |" for o in ORG_UNITS)
    defect_rows = "\n".join(
        f"| {d['index']} | {d['defect']} | {d['grant_no']} | {d['note']} |" for d in defect_log
    )
    license_rows = "\n".join(
        f"| {l['vendor']} | {l['product']} | {l['renews_on']} | {', '.join(l['datasets'])} |"
        for l in licenses
    )
    soon_cutoff = dt.date.today() + dt.timedelta(days=46)
    soon_licenses = [l for l in licenses if dt.date.fromisoformat(l["renews_on"]) <= soon_cutoff]

    return f"""# Synthetic Data Manifest — Compass demo

Generated by `scripts/seed_data.py` at `{generated_at}`. This document lists
**every** fixture under `seed/` and is the single place to check when asking
"is any of this real?"

## Assertion — no real CUI/PII

Every record in every file listed below is machine-generated from templates
and word lists in `scripts/seed_data.py`. There is no real person, no real
company, no real university, no real ONR/Navy program, no real award number,
and no real dollar figure anywhere in this repository's `seed/` directory.
Specifically:

- **Grant numbers** (`ONRD-<FY>-<PROGRAM>-<seq>`) use an invented prefix
  (`ONRD`) that does **not** match the real ONR/DoD contract-number format
  (`N00014-YY-N-NNNN`), specifically so nothing here can be confused with an
  actual award identifier.
- **Performer organizations** (`awardee`) are built from an invented
  prefix/suffix word list (`ORG_PREFIXES` × `UNIV_SUFFIXES`/`COMPANY_SUFFIXES`
  in `scripts/seed_data.py`) — no real university or company name is used.
- **Titles and abstracts** are assembled from templated technical vocabulary
  per program area — plausible-sounding S&T language, not copied from any
  real solicitation, award, or publication.
- **Dollar amounts** are randomly drawn from bands between $50,000 and
  $8,000,000 — not tied to any real budget line.
- **License vendor names** (Clarivate Web of Science, Dimensions, Crunchbase,
  Lens.org, Elsevier, PitchBook Data, CB Insights, GovTribe) ARE real
  commercial data-vendor/product names, used the way an internal IT asset
  registry would name a SaaS subscription ("we hold a Web of Science site
  license, N seats, renews on D"). No specific contract, invoice, price, or
  individual is fabricated — only generic administrative fields (seat counts,
  renewal date, an internal owning team). This was an explicit instruction
  from the build spec; flag for override if a fully fictional vendor list is
  preferred instead.
- **License owners** are internal team labels (e.g. "Portfolio Intelligence
  Team"), never a named person.
- `classification_band` values are `CUI-Mock` / `Public-Mock` — the `-Mock`
  suffix is intentional and permanent; this is demo data staged to *look like*
  a CUI-handling workflow, not actual CUI.

## Files

| File | Purpose | Records |
|---|---|---|
| `seed/grants_portfolio.json` | Baseline curated portfolio (`grants_curated` shape) | {len(portfolio)} |
| `seed/drops/drop_good.json` | Ingest demo: clean new batch, canonical fields | {len(drop_good)} |
| `seed/drops/drop_compatible_variant.json` | Ingest demo: renamed/reshaped columns the normalizer must map back | {len(drop_compat)} |
| `seed/drops/drop_incompatible_bad.json` | Ingest demo: missing/malformed rows that must be quarantined | {len(drop_bad)} |
| `seed/licenses.json` | Data-vendor license lifecycle records | {len(licenses)} |

Regenerate any time with `python3 scripts/seed_data.py` (zero dependencies —
stdlib only). Output is deterministic (`SEED = {SEED}`) except license
`renews_on` dates, which are intentionally computed relative to the run date
so the demo always looks current.

## `grants_portfolio.json` — distribution

By fiscal year:

| fiscal_year | count |
|---|---|
{fy_rows}

By program_area:

| program_area | count |
|---|---|
{prog_rows}

By org_unit:

| org_unit | count |
|---|---|
{org_rows}

Amount range: $50,000–$8,000,000 (banded: 35% $50k–250k, 35% $250k–1M, 20%
$1M–3M, 10% $3M–8M). `classification_band` is `CUI-Mock` for ~90% of rows and
`Public-Mock` for ~10%. `batch_id` is `seed-initial-2026` for every row in
this file.

## `drops/drop_good.json`

{len(drop_good)} new FY2026 grants, canonical `grants_curated` field names,
all fields present and well-typed. `batch_id = "drop-good-2026-08"`. Envelope
metadata: `source_file`, `schema_variant: "canonical"`.

## `drops/drop_compatible_variant.json`

The same kind of batch as above ({len(drop_compat)} new FY2026 grants) but
shaped like a real legacy exporter's file — renamed columns and two light
type differences the normalizer must handle:

| canonical field | variant field | transform needed |
|---|---|---|
| `grant_no` | `award_id` | rename only |
| `title` | `project_title` | rename only |
| `abstract` | `summary` | rename only |
| `program_area` | `portfolio_area` | rename only |
| `fiscal_year` | `fy` | rename + parse `"FY2026"` -> `2026` |
| `amount_usd` | `obligated_amount_usd` | rename + parse `"$1,234,567.00"` -> `1234567` |
| `awardee` | `performer_org` | rename only |
| `org_unit` | `command_code` | rename only |
| `classification_band` | `marking` | rename only |
| — | `source_system` | extra field not in canonical schema — normalizer should drop it |

Every record in this file is logically valid once normalized — nothing is
missing or corrupt, only differently named/shaped. `batch_id =
"drop-compat-2026-08"`.

## `drops/drop_incompatible_bad.json`

{len(drop_bad)} FY2026 rows using canonical field names (same names as
`drop_good.json` — the defect here is bad *values*, not renamed columns).
{len(defect_log)} rows carry a deliberate defect; the remaining
{len(drop_bad) - len(defect_log)} rows are clean. Expect a quality gate to
pass the clean rows and quarantine the defective ones (~{round(100 * (len(drop_bad) - len(defect_log)) / len(drop_bad))}% pass rate).
`batch_id = "drop-bad-2026-08"`.

Exact defect ledger (0-indexed position within the file's `records` array):

| index | defect | grant_no | note |
|---|---|---|---|
{defect_rows}

## `licenses.json`

{len(licenses)} data-vendor license records feeding the `licenses` table.
{len(soon_licenses)} renew within 45 days of generation time (the "renewing
soon" demo case):

| vendor | product | renews_on | linked datasets |
|---|---|---|---|
{license_rows}

`datasets` values are free-form labels (the `licenses.datasets` column is a
`TEXT[]`, not a foreign key) chosen to read naturally against whatever the
`/catalog` route surfaces: "Publication & Citation Index", "Patent Landscape
Feed", "Startup & Company Intelligence Feed", "Federal Contract Intelligence
Feed", "Grant Abstracts Corpus".
"""


# --------------------------------------------------------------------------- #
# Write + orchestrate
# --------------------------------------------------------------------------- #

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    rng = random.Random(SEED)
    seq = SeqCounter()
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    portfolio = build_main_portfolio(rng, seq)
    drop_good = build_drop_good(rng, seq)
    drop_compat_canonical_first_grant_no = drop_good[0]["grant_no"]  # for the duplicate-key defect
    drop_compat = build_drop_compatible(rng, seq)
    drop_bad, defect_log = build_drop_incompatible(rng, seq, duplicate_target=drop_compat_canonical_first_grant_no)
    licenses = build_licenses(rng)

    write_json(SEED_DIR / "grants_portfolio.json", {
        "dataset": "ONR S&T Grants Portfolio",
        "description": "Synthetic mock ONR Science & Technology grants portfolio for the Compass demo. No real CUI/PII.",
        "generated_at": now,
        "record_count": len(portfolio),
        "batch_id": "seed-initial-2026",
        "grants": portfolio,
    })

    write_json(DROPS_DIR / "drop_good.json", {
        "source_file": "gms_export_2026_08.json",
        "batch_id": "drop-good-2026-08",
        "dropped_at": now,
        "schema_variant": "canonical",
        "record_count": len(drop_good),
        "records": drop_good,
    })

    write_json(DROPS_DIR / "drop_compatible_variant.json", {
        "source_file": "legacy_gms_export_2026_08.json",
        "batch_id": "drop-compat-2026-08",
        "dropped_at": now,
        "schema_variant": "compatible-renamed",
        "record_count": len(drop_compat),
        "records": drop_compat,
    })

    write_json(DROPS_DIR / "drop_incompatible_bad.json", {
        "source_file": "partner_upload_2026_08_batch.json",
        "batch_id": "drop-bad-2026-08",
        "dropped_at": now,
        "schema_variant": "incompatible-malformed",
        "record_count": len(drop_bad),
        "records": drop_bad,
    })

    write_json(SEED_DIR / "licenses.json", {
        "generated_at": now,
        "record_count": len(licenses),
        "licenses": licenses,
    })

    manifest = build_manifest(portfolio, drop_good, drop_compat, drop_bad, defect_log, licenses, now)
    (SEED_DIR / "SYNTHETIC-DATA-MANIFEST.md").write_text(manifest, encoding="utf-8")

    print("Wrote:")
    for p in [
        SEED_DIR / "grants_portfolio.json",
        DROPS_DIR / "drop_good.json",
        DROPS_DIR / "drop_compatible_variant.json",
        DROPS_DIR / "drop_incompatible_bad.json",
        SEED_DIR / "licenses.json",
        SEED_DIR / "SYNTHETIC-DATA-MANIFEST.md",
    ]:
        print(f"  {p.relative_to(REPO_ROOT)}")
    print(f"\nPortfolio: {len(portfolio)} grants | drops: {len(drop_good)}+{len(drop_compat)}+{len(drop_bad)} "
          f"({len(defect_log)} defective) | licenses: {len(licenses)}")


if __name__ == "__main__":
    main()
