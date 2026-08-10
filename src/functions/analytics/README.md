# analytics — topic model + funding anomalies

`POST /analytics/run` / `GET /analytics/{run_id}` (see `docs/CONTRACTS.md`, element 5).

## Algorithm (real, not a stub)

Numpy-only **TF-IDF + NMF** over grant titles+abstracts, implemented from
first principles in `topic_model.py` (~150 lines of documented linear algebra):

1. Tokenize (regex word tokens, English + S&T-boilerplate stoplist).
2. Vocabulary: document-frequency filter (`min_df`, `max_df_ratio=0.5`),
   capped at 2000 terms.
3. TF-IDF with smoothed idf, L2-normalized rows.
4. NMF `X ≈ W·H` via Lee & Seung multiplicative updates (Frobenius norm),
   seeded `default_rng` → **deterministic** per `(corpus, k, seed)`;
   early-stops on relative reconstruction-error plateau.
5. Topics = rows of `H` (top-10 terms, top-3-term label); doc weights = rows
   of `W` normalized to 1; per-FY trend uses **within-FY share** so growth is
   not inflated by the portfolio adding more grants each year.
6. Funding anomalies: z-score of `amount_usd` within `program_area`
   (`|z| ≥ 3` high, `≥ 2.5` medium, groups ≥ 8) → `anomalies` table, deduped
   against existing open flags.
7. A concrete decision `recommendation` string is derived from the numbers
   (emerging topic, share growth over the trailing 2-FY window, anomaly count)
   and stored on `model_runs`.

Persisted per run, in one transaction: `model_runs`, `topics`,
`grant_topics`, `anomalies`, `lineage_nodes`/`lineage_edges`.

## Dependencies / Lambda fit

Only **numpy** (`requirements.txt`, pinned) on top of the psycopg2
CommonLayer. Chosen over scikit-learn on purpose: numpy alone is ~40 MB
unzipped (fits easily; sklearn+scipy would add ~170 MB and slow cold starts).
A 400-doc × 2000-term fit runs in well under a second at 1024 MB.

## Offline test

```
python3 -m venv .venv && .venv/bin/pip install numpy==2.2.6
.venv/bin/python src/functions/analytics/tests/test_topic_model.py
```

Runs against `seed/grants_portfolio.json` (synthetic corpus) — no AWS, no DB.
