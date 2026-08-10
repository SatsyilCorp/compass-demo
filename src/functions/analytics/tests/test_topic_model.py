"""Offline test for the numpy-only topic model — no AWS, no DB, no network.

Runs against the synthetic seed corpus (seed/grants_portfolio.json) when
present, plus a tiny hand-built corpus that must separate two obvious topics.

Run directly:  python3 tests/test_topic_model.py   (needs numpy only)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import topic_model  # noqa: E402

SEED_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "seed", "grants_portfolio.json"
)


def test_two_obvious_topics():
    """A corpus with two disjoint vocabularies must split cleanly at k=2."""
    quantum = "superconducting qubit coherence entanglement cryogenic microwave resonator"
    undersea = "sonar acoustic seawater hull submarine towed hydrophone array"
    docs = []
    for i in range(15):
        docs.append({"id": i, "title": "q", "abstract": quantum + f" run{i % 3}",
                     "program_area": "Quantum", "fiscal_year": 2024 + (i % 3)})
    for i in range(15):
        docs.append({"id": 100 + i, "title": "u", "abstract": undersea + f" dive{i % 3}",
                     "program_area": "Undersea", "fiscal_year": 2024 + (i % 3)})

    r = topic_model.fit_topics(docs, k=2, seed=7)
    assert len(r.topics) == 2, r.topics
    terms0, terms1 = (set(t["top_terms"]) for t in r.topics)
    q_terms = {"qubit", "entanglement", "cryogenic"}
    u_terms = {"sonar", "hydrophone", "submarine"}
    # Each hand-built theme's terms concentrate in exactly one topic.
    assert (q_terms & terms0 and u_terms & terms1) or (q_terms & terms1 and u_terms & terms0)
    # Determinism: same seed, same labels.
    r2 = topic_model.fit_topics(docs, k=2, seed=7)
    assert [t["label"] for t in r.topics] == [t["label"] for t in r2.topics]
    # Every doc got a dominant link with a sane weight.
    by_doc = {}
    for d in r.doc_topics:
        by_doc.setdefault(d["grant_id"], []).append(d["weight"])
    assert len(by_doc) == 30
    assert all(0.0 < max(ws) <= 1.0 for ws in by_doc.values())
    print("  two-topic separation: OK")


def test_zscore_anomalies():
    rows = [{"grant_id": i, "grant_no": f"G-{i}", "program_area": "AI/ML",
             "amount_usd": 100_000} for i in range(20)]
    rows[0]["amount_usd"] = 5_000_000  # blatant outlier
    # add jitter so std > 0
    for i in range(1, 20):
        rows[i]["amount_usd"] += i * 1_000
    flagged = topic_model.funding_zscores(rows)
    assert any(f["grant_id"] == 0 and f["severity"] == "high" for f in flagged), flagged
    assert all("$" in f["reason"] and "std devs" in f["reason"] for f in flagged)
    # Tiny groups are skipped.
    assert topic_model.funding_zscores(rows[:5]) == []
    print("  z-score anomalies: OK")


def test_seed_corpus():
    if not os.path.exists(SEED_FILE):
        print("  seed corpus: SKIPPED (seed/grants_portfolio.json not found)")
        return
    with open(SEED_FILE) as f:
        grants = json.load(f)["grants"]
    docs = [
        {"id": i, "title": g["title"], "abstract": g["abstract"],
         "program_area": g["program_area"], "fiscal_year": g["fiscal_year"]}
        for i, g in enumerate(grants)
    ]
    r = topic_model.fit_topics(docs, k=8, seed=20260810)
    assert r.metrics["n_docs"] == len(docs)
    assert len(r.topics) == 8
    assert all(len(t["top_terms"]) >= 5 for t in r.topics)
    assert all(t["trend"]["by_fy"] for t in r.topics)
    assert r.metrics["reconstruction_error"] < 1.0
    rec = topic_model.build_recommendation(r, [])
    assert "topic" in rec.lower() and len(rec) > 60
    print(f"  seed corpus ({len(docs)} grants): OK")
    print(f"    reconstruction_error={r.metrics['reconstruction_error']}")
    for t in r.topics:
        g = t["trend"]["growth_pct"]
        print(f"    [{t['topic_id']}] {t['label']:<40} growth={g}")
    print(f"    recommendation: {rec}")


if __name__ == "__main__":
    test_two_obvious_topics()
    test_zscore_anomalies()
    test_seed_corpus()
    print("all topic_model tests passed")
