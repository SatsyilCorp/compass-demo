"""Regression checks for browser-only live workflow boundaries."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cloudfront_csp_allows_the_signed_s3_upload_destination():
    template = (ROOT / "template.yaml").read_text(encoding="utf-8")
    policy = template.split("ContentSecurityPolicy: >-", 1)[1].split(
        "Override: true", 1
    )[0]

    assert "https://*.execute-api.us-east-1.amazonaws.com" in policy
    assert "https://*.s3.amazonaws.com" in policy


def test_expanded_catalog_lineage_link_uses_the_static_query_route():
    component = (
        ROOT / "frontend/components/catalog/quality-panel.tsx"
    ).read_text(encoding="utf-8")
    route = (
        ROOT / "frontend/components/catalog/lineage-route.ts"
    ).read_text(encoding="utf-8")

    assert "href={catalogLineageHref(entry.id)}" in component
    assert "`/catalog/lineage/?batch=${encodeURIComponent(batchId)}`" in route
    assert "href={`/catalog/${encodeURIComponent(entry.id)}/`}" not in component


def test_document_receipt_opens_the_exact_authoritative_run():
    component = (
        ROOT / "frontend/components/documents/document-drop-zone.tsx"
    ).read_text(encoding="utf-8")

    assert (
        "href={`/admin/lineage/?run=${encodeURIComponent(liveRun.run_id)}`}"
        in component
    )


def test_live_network_failures_have_presenter_safe_recovery_messages():
    api = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")

    assert "The live Compass service could not be reached. Refresh and retry." in api
    assert "The browser could not reach the governed S3 intake boundary." in api
