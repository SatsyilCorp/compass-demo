# Compass public intelligence collectors

This package collects bounded snapshots from authoritative public award and
research sources. It is intentionally independent from the Compass application
and AWS deployment so that collection, review, and promotion can be controlled
as a separate data supply chain.

Implemented sources:

* USAspending Advanced Award Search API
* SBIR and STTR full monthly award CSV
* Crossref Works API
* OpenAlex Works API
* PubMed E-utilities with exact `N00014[Grant Number]` indexing
* OSTI.GOV API with exact Office of Naval Research sponsor filtering
* Grants.gov DOD-ONR opportunity search and detail APIs
* SAM.gov public Opportunities API scoped to the ONR organization hierarchy
* DataCite DOI API filtered by the ONR ROR identifier
* Federal Register API filtered to the Navy Department and an exact ONR phrase
* USPTO ODP PatentsView bulk tables joined on exact ONR government interest
* Official ONR public HTML sitemap, with robots rules checked on every run

The accepted 2026-08-12 collection corpus contains 177,503 minimized canonical
records across these 12 persisted public source families. The compact
interactive Serving Projection is a bounded sample and must not be reported as
the full corpus. Exact per-source counts and evidence boundaries are recorded
in `../docs/PUBLIC_ONR_INTELLIGENCE.md`.

The registry also records sources that require an API key, a license, or a
government-controlled manual transfer. Listing a source does not claim access.

## Safety and data handling

Every run has an explicit record ceiling. The default is 10,000 records and the
hard ceiling is 2,000,000 records. HTTP requests have timeouts, retry limits,
rate limits, and a descriptive user agent. The SBIR archive stream has a byte
ceiling and is never persisted locally. Checkpoints record the source row and
HTTP version identifier. A resumed run streams from the beginning and discards
rows already committed. This avoids retaining a raw PII-bearing archive.

SBIR contact names, email addresses, telephone numbers, fax numbers, and street
addresses are removed before a source row is mapped or hashed. Email, phone,
and Social Security number patterns are also redacted from retained text.
Crossref and OpenAlex author names and personal identifiers are not placed in
the canonical record. DataCite creator and contributor identities are also
omitted. Author counts and institution names remain available. Grants.gov
contact names, phone numbers, email addresses, and contact descriptions are
not retained.

SAM.gov collection requires `SAM_GOV_API_KEY` in the process environment. The
key is never accepted as a command-line argument, persisted in a checkpoint,
or placed in a provenance URL. HTTP errors redact credential-bearing query
parameters. The connector retains public opportunity metadata and broad place
geography while omitting points of contact, description bodies, attachment
URLs, street addresses, ZIP codes, and API self links.

PubMed collection uses the exact `N00014[Grant Number]` query and omits author
identities plus publisher-controlled abstract text. It retains PMID, DOI, PMCID,
grant identifiers, journal, publication date, MeSH headings, keywords, and
source citations. The NCBI date query is also enforced locally before a record
is persisted. The 2026-08-11 evidence snapshot contains 1,595 records, with
researcher identities and copyrighted abstract text omitted.

The USPTO patent collector reads only the granted-patent metadata, government
interest organization, government interest contract, and government interest
statement tables in the official `PVGPATDIS` ODP product. A patent is retained
only when PatentsView reports an exact `Office of Naval Research` organization
or an award whose punctuation-folded value starts with `N00014`. Inventor,
attorney, applicant, assignee-person, and address tables are never read. Patent
abstracts and government-interest statement text are not persisted. The
sanitized statement digest, source table digests, exact match basis, patent
number, title, grant date, organization hierarchy, and extracted award numbers
remain available for lineage and analyst review. The 2026-08-12 evidence
snapshot contains 5,388 unique patent grants through 2025-12-31. Of those,
4,944 have an exact normalized `N00014` prefix, 1,845 have an exact ONR
organization, and 1,401 satisfy both tests.

Records contain two SHA-256 values:

* `source_payload_sha256` hashes the sanitized source payload.
* `record_sha256` hashes the stable canonical record fields and excludes
  collection time, snapshot ID, and itself.

This gives deterministic lineage without persisting direct contact data.
The machine-readable contract is
`schemas/canonical-record.schema.json`.

## Install and run

```bash
cd public_intelligence
python3 -m pip install -e .
compass-public-intel list-sources
compass-public-intel collect usaspending \
  --output snapshots/usaspending.jsonl \
  --from-date 2024-01-01 \
  --to-date 2026-08-11 \
  --max-records 10000
```

Crossref requests should include a contact address:

```bash
compass-public-intel collect crossref \
  --mailto data-team@example.org \
  --query "autonomous maritime systems" \
  --output snapshots/crossref.jsonl \
  --max-records 25000
```

Collect public ONR opportunity notices and their public detail records:

```bash
compass-public-intel collect grants_gov \
  --from-date 2000-01-01 \
  --output snapshots/grants-gov.jsonl \
  --max-records 1000
```

The Grants.gov source defaults to the exact agency code `DOD-ONR`, all public
opportunity statuses, and stable ascending open-date pagination. Detail calls
can be disabled with `--grants-skip-details`, but the default retains the
substantive synopsis after removing contact fields.

Collect public SAM.gov notices under the exact ONR organization hierarchy:

```bash
SAM_GOV_API_KEY='<retrieve through an approved secret channel>' \
compass-public-intel collect sam_gov \
  --from-date 2025-08-12 \
  --to-date 2026-08-11 \
  --output snapshots/sam-gov-onr.jsonl.gz \
  --gzip \
  --max-records 10000
```

The default `organizationCode` is `017.1700.ONR`. Every returned record must
match that code or a descendant path before it can be persisted. Date ranges
are divided into API-safe windows of no more than 365 days. Run keyed refreshes
only inside a source-owner-approved quota window. A bounded 2026-08-01 cache
recovery scanned 923 public notices from 104 existing Satsyil GovSentry API
pages limited to NAICS 541511, 541512, and 541519, then retained 5 exact ONR
descendants. That partial snapshot proves the mapping and privacy controls,
but it is not a comprehensive SAM.gov history.

Collect public research outputs that DataCite links to ONR's canonical ROR:

```bash
compass-public-intel collect datacite \
  --from-date 2000-01-01 \
  --output snapshots/datacite.jsonl \
  --max-records 5000
```

DataCite metadata is CC0. Rights for linked datasets, software, publications,
and other content remain source-specific and are retained in each record when
available. The collector does not download linked content.

Collect PubMed records carrying an exact N00014 grant-number index:

```bash
compass-public-intel collect pubmed \
  --from-date 1900-01-01 \
  --to-date 2026-08-11 \
  --mailto data-team@example.org \
  --output snapshots/pubmed-n00014.jsonl.gz \
  --gzip \
  --max-records 5000
```

NCBI recommends a registered tool email, and an NCBI API key increases the
supported request rate. Compass stays at two requests per second by default.
PubMed abstracts may be copyrighted, so the connector records only whether an
abstract exists and does not persist its text.

Collect public Navy notices that mention the Office of Naval Research:

```bash
compass-public-intel collect federal_register \
  --from-date 2000-01-01 \
  --output snapshots/federal-register.jsonl.gz \
  --gzip \
  --max-records 5000
```

The default term is the exact phrase `"Office of Naval Research"` and the
default agency slug is `navy-department`. Use `--query` only when a broader
scope has been reviewed. The connector retains Federal Register metadata,
docket identifiers, comment deadlines, and official GovInfo PDF links. It does
not download document bodies or public comments. FederalRegister.gov is a
convenient web rendition, not the legal edition, so users should follow the
GovInfo PDF link for legal reliance.

Collect public ONR program and topic page headings from the official site index:

```bash
compass-public-intel collect onr_website \
  --output snapshots/onr-website-index.jsonl.gz \
  --gzip \
  --max-records 1000 \
  --max-pages 1 \
  --requests-per-second 0.25
```

The connector retrieves `robots.txt` first and refuses the run if `/sitemap`
is disallowed. The official robots file observed on 2026-08-12 allowed the
public HTML sitemap while blocking administrative, search, and filter routes.
The XML sitemap endpoint did not provide a stable collection response, so the
connector uses only the official HTML site index. It never fetches linked page
bodies, PDFs, office documents, or external sites. Personnel, contact, career,
location, and administration lookup pages are excluded before canonicalization.
The accepted 2026-08-12 snapshot contains 308 unique official page headings,
including 169 research-program entries. Content publication dates are not
present in the HTML sitemap, so records leave that field empty and preserve the
retrieval timestamp in provenance.

Collect ONR-linked granted patents from the official USPTO ODP PatentsView
tables. Load the key into the environment through an approved secret injector.
Do not place the value in the command line or shell history:

```bash
test -n "${USPTO_ODP_API_KEY:?Load USPTO_ODP_API_KEY through the approved secret store}"
compass-public-intel collect uspto_patents \
  --from-date 1976-01-01 \
  --to-date 2025-12-31 \
  --output snapshots/uspto-patents-onr.jsonl.gz \
  --gzip \
  --max-records 10000
```

The upstream key is sent only in the `X-API-Key` request header. It is never
placed in a URL, canonical record, checkpoint, or download cache. ODP currently
publishes the joined product through 2025-12-31. Use
`--uspto-refresh-cache` for a deliberate source refresh. PatentsView applies CC
BY 4.0 to the product and documents known extraction error, so an exact match is
evidence for review rather than an unqualified causal claim about ONR impact.

Department of the Navy budget materials are declared in the registry but are
not collected automatically. The current public SharePoint edge rejects
automated clients. Compass does not bypass that control. An approved direct
document manifest or manual transfer can be added later with document-level
provenance and rights review.

`--max-pages` places a second bound on API collection. It defaults to 10,000
and prevents a malformed or cyclic cursor response from running indefinitely.

The official SBIR archive is large. It is streamed row by row and filtered to
Navy awards by default, so neither memory nor local disk use grows with the file
size:

```bash
compass-public-intel collect sbir \
  --output snapshots/sbir \
  --format parquet \
  --max-records 250000
```

Use `--sbir-branch-filter all` only when a broader snapshot has been approved.
The raw archive is still not stored.

Parquet output requires `python3 -m pip install -e '.[parquet]'`. JSONL uses
only the Python standard library. Add `--gzip` or use an output name ending in
`.gz` for resumable gzip JSONL.

Resume is enabled by default. The checkpoint is stored next to the output. Use
`--fresh` only when intentionally replacing a partial snapshot. Increasing
`--max-records` continues the same compatible snapshot.

## Offline tests

```bash
cd public_intelligence
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

All connector tests use local fixtures. They do not call public services.
