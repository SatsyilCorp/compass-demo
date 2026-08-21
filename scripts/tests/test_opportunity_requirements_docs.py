from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "docs" / "OPPORTUNITY_REQUIREMENTS_BOUNDARY.md"
REQUIRED_FACTS = (
    "1Gb5Kvt-B9TrJj8h6QpFkJu_4OhGyYQXm",
    "18k-L24gQBBVpa0zhGPeoCOkyzx5CYTdi",
    "1ONxTKw-4HLPiVLbwJD_7WOt4lHS57JX5",
    "N0001426R4002",
    "500 to 1,000 total users",
    "200 to 300 power users",
    "10 to 20 source systems",
    "1 to 20 TB managed data",
    "At least 1 TB of annual growth",
    "Daily incremental and full refresh patterns",
    "50 to 75 Tier 1 and Tier 2 tickets per month",
    "99 percent uptime during core hours",
    "95 percent ticket service-level attainment",
    "Cloud-log inspection",
    "FinOps",
    "Responsible AI review",
    "no public commercial AI used for CUI",
    "IL5 and FedRAMP High",
)


def test_opportunity_requirements_record_authoritative_targets_and_boundaries():
    content = REQUIREMENTS.read_text(encoding="utf-8")

    for fact in REQUIRED_FACTS:
        assert fact in content
    assert "Government-only or proprietary" in content
    assert "remains outside the public corpus" in content
    assert "not an accredited Government environment" in content
    assert "100 to 200 concurrent users" not in content
    assert "\u2014" not in content
