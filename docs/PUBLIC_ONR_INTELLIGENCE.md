# Public ONR intelligence data contract

## Purpose

Compass can use public ONR and Navy evidence for real portfolio analysis while
retaining synthetic records only for scale, fault, and resilience testing. The
public corpus is not an ONR internal system and does not contain authoritative
internal milestone, readiness, mission-impact, or project-success decisions.

Every product measure must be labeled as one of:

* `observed`: directly reported by an identified public source.
* `derived`: computed deterministically from observed records.
* `predicted`: produced by a versioned model and accompanied by uncertainty.

## Source registry

| Source | Scope | Retrieval | Primary keys | Data boundary |
|---|---|---|---|---|
| USAspending | Awards, contracts, obligations, transactions | Public API and bulk snapshot | generated award ID, PIID, FAIN, UEI, action date | Require Department of the Navy plus exact ONR awarding or funding office where available. |
| SBA SBIR and STTR | Phase I and Phase II awards, topics, abstracts | Monthly public CSV | UEI, contract, tracking number, solicitation, topic, phase | Drop contacts, phone, email, address lines, ZIP, and protected selection attributes. Navy alone does not mean ONR. |
| Grants.gov | ONR assistance opportunities | Public API | opportunity ID and number, ALN | Filter agency `DOD-ONR`; remove agency contact fields. |
| SAM.gov Opportunities | Contract notices and solicitations | API key required | notice ID, solicitation, organization code | Do not download restricted or access-labeled attachments. Drop point-of-contact fields. |
| DoD and Navy budget exhibits | R-1, R-2, and R-2A budget evidence | Versioned public PDFs | fiscal year, appropriation, PE, project | Preserve page and table coordinates. Use a reviewed program crosswalk. |
| Crossref | ONR-funded publications | Public REST API | DOI, funder DOI, exact award number | Retain metadata. Do not retain abstracts unless the record license permits it. |
| OpenAlex | Works, concepts, institutions, citations | Public REST API | OpenAlex work, DOI, funder ID, award ID | Treat as an enrichment source and reconcile against primary identifiers. |
| PubMed | Biomedical publications with ONR contract identifiers | NCBI E-utilities | PMID, DOI, PMCID, exact N00014 grant number | Omit researcher identities and abstract text. Retain controlled subject terms and source links. |
| OSTI.GOV | Public research records sponsored by ONR | Public REST API | OSTI ID, DOI, report number, non-DOE contract number | Omit researcher identities and description text pending rights review. Retain sponsor, institution, subjects, and citation links. |
| DataCite | Datasets and software | Public REST API | DOI, funding award number, related identifiers | Metadata is reusable; linked content retains its own rights. |
| USPTO ODP | Patents and Government interest | API key and bulk products | patent ID, Government-interest award number | Omit inventor profiling and addresses. Validate Navy award extraction before use. |
| Official ONR website | Program, topic, organization, funding, and outreach page headings | Robots-aware public HTML sitemap | Drupal node ID and canonical page path | Fetch only `robots.txt` and `/sitemap`. Exclude linked page bodies, documents, external sites, personnel pages, contact pages, and direct PII. |
| DTIC | Public grant abstracts and reports | Public or approved manual access | award number and report ID | Never bypass access controls or ingest distribution-limited material. |

## Source acquisition status

The acquisition registry separates what is actually present from what is only
planned or intentionally excluded. A declared category is not a live
connection.

| State | Sources or categories | Activation requirement | Current boundary |
|---|---|---|---|
| Collected public | USAspending; SBIR and STTR; Grants.gov; SAM.gov; DataCite; Crossref; OpenAlex; PubMed; OSTI.GOV; USPTO PatentsView; Federal Register; official ONR website index | Public access plus any required API key, quota window, rights review, minimization, and governed promotion | 177,503 minimized records across 12 source families are in the accepted evidence package. Public evidence is not authoritative ONR operational truth. |
| Licensed and commercial | Startup investment intelligence; company ownership, profile, and financial intelligence; informal literature, commercial news, and market research | Government-provided or approved license, API or export rights, data-use review, and retention and redistribution rules | No vendor is selected and no licensed commercial records are collected. |
| Government-furnished | Advana; Pulse; restricted DTIC; Navy budget SharePoint materials; structured Government acquisition and scientific reports; unstructured Government reports and documents | Government-furnished access, data-use agreement, distribution or CUI review, approved transfer, and source-specific schema and rights review | No live connection to these systems or collections is claimed, and no restricted Government records are collected. |
| Intentionally excluded | Restricted opportunity documents, controlled attachments, and access-labeled notices | Explicit source-owner authorization, distribution review, and an approved Government processing boundary | Public opportunity metadata is collected. Protected attachments and controlled documents are not fetched, indexed, embedded, or used for training. |

## Public snapshot completed on 2026-08-12

The accepted collection corpus contains 177,503 minimized canonical records across
12 persisted public source families. This full corpus is separate from the
bounded Serving Projection used for interactive queries. After governed
promotion, that projection contains a deterministic 1,096-record source sample
plus two model-evidence records, for 1,098 indexed records. The 1,098 count is
the query-optimized sample size, not the corpus size. The complete 12-source
evidence package, including the ONR website index, is retained in the encrypted
evidence lake with source manifests, checkpoints, and SHA-256 digests.

| Source | Observed volume | Current state |
|---|---:|---|
| USAspending | 20,776 deduplicated candidate records, including 13,300 grants and 7,476 contracts | Persisted in the encrypted Satsyil data lake with SHA-256 `a3c6107463f75ee6d8f15b73580cfe3c1d122c42b8d7ce8f8501de86e156b509`. The $19,260,405,492.79 summed award amount is candidate-scope evidence, not an authoritative ONR total. |
| SBA SBIR and STTR | 27,887 Navy records | Corrected snapshot persisted with direct PII removed and public award identifiers retained. Navy does not imply ONR without an exact link. |
| Grants.gov | 286 `DOD-ONR` opportunities | Persisted with detail records and contact fields removed. |
| SAM.gov Opportunities | 5 exact `017.1700.ONR` descendants in a bounded cache recovery | Persisted from 104 authorized Satsyil GovSentry public API cache pages limited to NAICS 541511, 541512, and 541519 through 2026-08-01 after scanning 923 notices. Contacts, descriptions, attachment URLs, street addresses, ZIP codes, and API self links were omitted. This proves the connector and controls, not a comprehensive SAM.gov history. |
| DataCite | 498 ONR ROR-funded outputs | Persisted with creator, contributor, and ORCID identities omitted. |
| Crossref | 48,747 ONR funder works through the cutoff | Full metadata snapshot persisted. Publisher abstract text is not persisted without an explicit reuse right. |
| OpenAlex | 68,912 ONR funder-linked works through the cutoff | Persisted from four non-overlapping date partitions after exact-funder validation. An earlier incorrectly scoped partial was quarantined and never uploaded. Reconstructed abstracts are redacted when direct PII is detected. |
| PubMed | 1,595 records returned by exact `N00014[Grant Number]` query | Persisted with PMID, DOI, PMCID, grant metadata, journal, dates, subject terms, and source links where present. Author identities and abstract text are omitted. Query membership is preserved without claiming every source XML record repeats a clean N00014 value. |
| OSTI.GOV | 3,010 records returned by exact `Office of Naval Research` sponsor filter | Persisted with OSTI ID, DOI, report and contract identifiers, sponsor, institution, subjects, and citation links. Researcher identities and description text are omitted pending rights review. |
| USPTO ODP PatentsView | 5,388 patent grants with exact ONR government-interest evidence through 2025-12-31 | Persisted from four digest-bound official ODP tables with canonical snapshot SHA-256 `5e520b0b9eec14e241426357bb3900b801e8658617274abc42ba928e4124b145`. 4,944 records have a punctuation-folded `N00014` award prefix, 1,845 have an exact `Office of Naval Research` organization, and 1,401 satisfy both. Inventor, attorney, applicant, assignee-person, address, abstract, and government-interest statement text are omitted. PatentsView extraction remains subject to documented source error and analyst review. |
| Federal Register | 91 Navy agency documents matching `Office of Naval Research` | Metadata snapshot persisted with dockets, RINs, CFR references, dates, and 91 official GovInfo links. No bodies or public comments were downloaded. |
| Official ONR website | 308 unique official page headings, including 169 research-program entries | Collected on 2026-08-12 from the public HTML sitemap after validating the live robots policy. Only exact `www.onr.navy.mil` HTTPS links, headings, hierarchy, page type, and Drupal node IDs were retained. Linked pages, documents, staff and contact pages, external links, and direct PII were omitted. Sitemap publication dates were unavailable and are not inferred. |

The SAM.gov connector is implemented, but a fresh comprehensive pull still
requires `SAM_GOV_API_KEY` and a source-owner-approved quota window. The
dedicated development secret is intentionally disabled, so the existing
production workload key was not consumed outside its quota discipline. Advana needs Government-furnished access and a data-use
agreement. Pulse, restricted DTIC, Navy budget SharePoint, and Government
report sources require source-owner authorization, distribution review, and an
approved transfer. Scopus and any startup, company, or informal-literature
provider require approved licensing and rights review. None of those gated
sources contributes records to the current corpus.

## Entity and lineage contract

Raw identifiers are immutable. A normalized comparison form may uppercase and
remove whitespace and punctuation, but it never replaces the source value.

* Tier A link: exact PIID, FAIN, award number, opportunity number, DOI funding
  award, or UEI.
* Tier B link: exact UEI plus solicitation or topic plus temporal consistency,
  with a second corroborating source.
* Tier C link: title, organization, or semantic similarity. This produces a
  review candidate only and cannot publish an asserted relationship.

Every graph edge records both source records, rule, confidence tier, snapshot
cutoff, code version, and reviewer state.

## Model contracts

### Funding flow forecast

Predict the next four quarters of obligated amount at portfolio, program, and
technology-area grains. Compare hierarchical quantile gradient boosting with
seasonal naive and statistical baselines. Use rolling-origin evaluation and
report WAPE, MASE, MAE, pinball loss, and interval coverage. A forecast is not
a budget commitment or allocation recommendation.

The first real candidate used 76 public USAspending quarters. FY2026 Q4 was
excluded as incomplete, four earlier quarters supplied leakage-safe lag
features, and 71 authentic rows remained. A Random Forest with a held-out
conformal interval used 43 fit, 14 calibration, and 14 chronological test rows.
Measured holdout MAE was $125.39 million, RMSE was $156.03 million, and the
nominal 90% interval covered 85.71% of the holdout rows. The package is in
SageMaker Model Registry as `PendingManualApproval`. It has no endpoint and is
not a production-accuracy claim.

### SBIR Phase I to Phase II transition

The event is an observed later Phase II record within a declared 24 or 36 month
horizon. Recent awards without a complete horizon are censored, not negative.
Split by solicitation year and group by UEI and topic. Report Brier score,
calibration, PR-AUC, concordance, and recall at a fixed analyst capacity. No
post-outcome feature may enter training.

The first authentic candidate used 11,287 complete-horizon examples derived
from 27,887 public Navy SBIR and STTR records. The target is a later public
Phase II or Phase III record for the same normalized organization and exact
topic within 36 months of its earliest Phase I record. Organization names are
used to construct the label and leakage-safe split groups, not as model
features. A calibrated histogram gradient-boosted tree combines bounded
numeric and categorical features with TF-IDF and SVD text features. The fully
chronological 2019 to 2023 test set contains 2,260 records. The network-isolated
SageMaker job `compass-doc-sbir-transition-20260812-0134` completed in 109
billable seconds using the managed scikit-learn 1.4-2 image. Measured ROC AUC is
0.6264, Brier score is 0.2617, F1 is 0.5703, precision is 0.4304, and recall is
0.8453. Package version 2 is `PendingManualApproval`; version 1 was rejected
before deployment after its inference layout was found to be incomplete. No
endpoint exists. This is a real candidate with modest performance, not a
production accuracy claim, an ONR mission-success score, or a deployment
authorization.

### Federal follow-on proxy

Link later non-SBIR federal obligations to the same UEI only when award identity,
time, and technology similarity support the connection. Label this `federal
follow-on proxy`, never commercialization, mission success, or Phase III unless
the public record explicitly says Phase III.

### Technology intelligence

Use TF-IDF and NMF for stable, inspectable theme discovery. Use a calibrated
linear classifier only when a reviewed taxonomy label exists. Remove topic codes
and templated label strings from model text. Report stability across time and
seeds, macro F1 for supervised labels, retrieval precision, and SME agreement.

### Research impact

Model direct output evidence separately: award-linked publication, patent,
dataset, or software within a fixed horizon. Use a two-part or survival model
when censoring is substantial. Citation measures use fixed-age windows and
field normalization. Research output is a success indicator, not causal proof
of mission impact.

### Portfolio anomaly detection

Apply deterministic data-quality rules before robust peer-normalized scores and
Isolation Forest. Report alert rate and analyst precision at a fixed review
budget. The product says `unusual transaction for review`, never fraud, waste,
or failure.

### Success evidence view

Do not train a universal black-box success label. Display the observed and
predicted components independently:

* Phase II transition
* Explicit Phase III evidence
* Federal follow-on proxy
* Award-linked publication
* Award-linked patent
* Award-linked dataset or software
* Fixed-age field-normalized citation evidence

Any scenario weighting is an analyst-selected decision lens, not ground truth.

## Citation-grounded explanation

The explanation model receives only policy-visible retrieved passages and model
evidence. Every material claim carries a source record citation. Each chunk
stores source URL, section or page, identifiers, publication and retrieval
dates, SHA-256, license or access label, and as-of date. The assistant refuses
an answer when supporting evidence is absent.

Evaluation includes retrieval Recall at K, nDCG, MRR, citation precision,
faithfulness, temporal leakage, and refusal behavior. An LLM answer is never a
training label.

## Nonnegotiable controls

1. Use temporal as-of splits and grouped entity splits.
2. Treat missing future evidence as censored or unknown, not automatically false.
3. Remove unnecessary direct PII before Silver storage.
4. Never request or store SAM sensitivity-controlled fields.
5. Keep protected business designations out of selection models. They may be
   used only for controlled subgroup error audits.
6. Version raw snapshots, schemas, source parameters, feature manifests, label
   manifests, code, model artifacts, and evaluation receipts.
7. Display record coverage and link precision beside model performance.
8. Preserve the public and synthetic corpora as distinct evidence sets.
