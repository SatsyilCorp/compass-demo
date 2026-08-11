# Synthetic document drop set

Every file in this directory is deterministic synthetic demonstration data.
No record represents a real person, award, company, patent, publication, or
financial execution report.

- `technical-report.txt`: unstructured document expected to pass and classify
  as `technical_report`.
- `grant-abstract.json`: semi-structured document expected to pass and classify
  as `grant_abstract`.
- `financial-execution.csv`: tabular document expected to pass and classify as
  `financial_execution`.
- `patent-summary.md`: unstructured document expected to pass and classify as
  `patent_summary`.
- `investment-brief.txt`: unstructured document expected to pass and classify
  as `investment_brief`.
- `publication-summary.json`: semi-structured document expected to pass and
  classify as `publication_summary`.
- `quarantine-short.txt`: too little extractable content, expected to fail the
  blocking quality gate and enter quarantine.
