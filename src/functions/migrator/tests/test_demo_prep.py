"""Offline safety and contract tests for demo preparation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / "src" / "functions" / "migrator" / "demo_prep.py"
SPEC = importlib.util.spec_from_file_location("compass_demo_prep", MODULE_PATH)
assert SPEC and SPEC.loader
demo_prep = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demo_prep
SPEC.loader.exec_module(demo_prep)

SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "compass_prepare_demo_script",
    ROOT / "scripts" / "prepare_demo.py",
)
assert SCRIPT_SPEC and SCRIPT_SPEC.loader
prepare_script = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = prepare_script
SCRIPT_SPEC.loader.exec_module(prepare_script)


FIXTURE_PATHS = {
    "portfolio": ROOT / "seed" / "grants_portfolio.json",
    "licenses": ROOT / "seed" / "licenses.json",
    "drop_good": ROOT / "seed" / "drops" / "drop_good.json",
    "drop_compatible": ROOT / "seed" / "drops" / "drop_compatible_variant.json",
    "drop_bad": ROOT / "seed" / "drops" / "drop_incompatible_bad.json",
}


def fixture_payloads():
    return {name: json.loads(path.read_text()) for name, path in FIXTURE_PATHS.items()}


def test_all_committed_fixtures_satisfy_the_synthetic_contract():
    for name, payload in fixture_payloads().items():
        demo_prep.validate_fixture(name, payload)


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        ("portfolio", lambda p: p.update(synthetic_only=False)),
        ("portfolio", lambda p: p.update(batch_id="caller-selected-batch")),
        ("portfolio", lambda p: p["grants"][0].update(classification_band="SECRET")),
        ("licenses", lambda p: p["licenses"][0].update(vendor="Unapproved Vendor")),
        ("drop_good", lambda p: p.update(batch_id="different-drop")),
    ],
)
def test_fixture_validation_rejects_scope_expansion(name, mutate):
    payload = deepcopy(fixture_payloads()[name])
    mutate(payload)
    with pytest.raises(demo_prep.DemoPreparationError):
        demo_prep.validate_fixture(name, payload)


class FakeS3:
    def __init__(self, payloads, *, corrupt_metadata_for=None):
        self.by_key = {
            demo_prep.STAGED_FIXTURES[name]: json.dumps(payload, separators=(",", ":")).encode()
            for name, payload in payloads.items()
        }
        self.corrupt_metadata_for = corrupt_metadata_for

    def get_object(self, *, Bucket, Key):
        assert Bucket == "physical-name-hidden-from-receipt"
        body = self.by_key[Key]
        digest = hashlib.sha256(body).hexdigest()
        if Key == self.corrupt_metadata_for:
            digest = "0" * 64
        return {
            "Body": io.BytesIO(body),
            "Metadata": {
                "fixture-sha256": digest,
                "synthetic-only": "true",
            },
        }


def test_staged_fixture_receipts_are_validated_and_redacted(monkeypatch):
    monkeypatch.setenv("DEMO_FIXTURE_BUCKET", "physical-name-hidden-from-receipt")
    loaded = demo_prep.load_staged_fixtures(FakeS3(fixture_payloads()))
    receipt = json.dumps([fixture.receipt() for fixture in loaded.values()])
    assert len(loaded) == 5
    assert "physical-name-hidden-from-receipt" not in receipt
    assert "demo-stage/" not in receipt
    assert "staged://portfolio" in receipt


def test_staged_fixture_hash_mismatch_fails_closed(monkeypatch):
    monkeypatch.setenv("DEMO_FIXTURE_BUCKET", "physical-name-hidden-from-receipt")
    bad_key = demo_prep.STAGED_FIXTURES["portfolio"]
    with pytest.raises(demo_prep.DemoPreparationError, match="hash"):
        demo_prep.load_staged_fixtures(
            FakeS3(fixture_payloads(), corrupt_metadata_for=bad_key)
        )


class ResetCursor:
    def __init__(self, *, non_demo=0):
        self.non_demo = non_demo
        self.rows = []
        self.rowcount = 0
        self.calls = []

    def execute(self, query, params=None):
        text = str(query)
        self.calls.append((text, params))
        self.rowcount = 0
        if text.startswith("SELECT count(*) FROM grants_curated"):
            self.rows = [(self.non_demo,)]
        elif text.startswith("SELECT run_id FROM model_runs"):
            self.rows = [("tm-demo-prior",)]
        elif text.startswith("DELETE"):
            self.rowcount = 1
            self.rows = []

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return list(self.rows)


def test_reset_refuses_to_run_beside_non_demo_curated_data():
    cur = ResetCursor(non_demo=1)
    with pytest.raises(demo_prep.DemoPreparationError, match="non-demo"):
        demo_prep.reset_synthetic_state(cur)
    assert not any(query.startswith("DELETE") for query, _ in cur.calls)


@pytest.mark.parametrize(
    "query_marker",
    [
        "FROM licenses WHERE NOT",
        "FROM approvals",
        "FROM model_runs WHERE NOT",
        "FROM anomalies WHERE NOT",
        "FROM lineage_nodes WHERE NOT",
    ],
)
def test_reset_refuses_unexpected_ui_driving_state(query_marker):
    class UnexpectedStateCursor(ResetCursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            self.rows = [(1 if query_marker in str(query) else 0,)]

    cur = UnexpectedStateCursor()
    with pytest.raises(demo_prep.DemoPreparationError, match="non-demo state"):
        demo_prep.reset_synthetic_state(cur)
    assert not any(query.startswith("DELETE") for query, _ in cur.calls)


def test_reset_deletes_only_fixed_synthetic_scopes_and_keeps_audit():
    cur = ResetCursor()
    counts = demo_prep.reset_synthetic_state(cur)
    deletes = [(query, params) for query, params in cur.calls if query.startswith("DELETE")]
    assert counts
    assert deletes
    assert all("audit_log" not in query for query, _ in deletes)
    assert any("requested_by = ANY" in query for query, _ in deletes if "approvals" in query)
    assert sum("DELETE FROM licenses WHERE vendor = %s AND product = %s" in query for query, _ in deletes) == 8
    serialized_params = json.dumps([params for _, params in deletes], default=str)
    for batch_id in demo_prep.DEMO_BATCH_IDS:
        assert batch_id in serialized_params
    for username in demo_prep.DEMO_USERS:
        assert username in serialized_params


class FinalizeCursor:
    def __init__(self):
        self.calls = []
        self.rowcount = 0
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        text = str(query)
        self.calls.append((text, params))
        if text.startswith("SELECT kind"):
            self.rows = [
                (
                    "topic_model",
                    {
                        "requested_by": demo_prep.DEMO_ANALYTICS_ACTOR,
                        "org_unit": "ONR-Corporate",
                    },
                    {"n_docs": 400, "k": 8},
                )
            ]
        elif text.startswith("SELECT count(*) FROM topics"):
            self.rows = [(8,)]
        elif text.startswith("SELECT count(*) FROM grant_topics"):
            self.rows = [(640,)]
        else:
            self.rows = []
            self.rowcount = 1

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_finalize_tags_only_a_matching_real_baseline_analytics_run():
    cursor = FinalizeCursor()
    conn = Connection(cursor)
    run_id = "tm-20260810123456-abcdef12"
    receipt = demo_prep.finalize_analytics(conn, run_id)
    assert receipt == {
        "schema_version": demo_prep.PREFLIGHT_SCHEMA,
        "status": "analytics_ready",
        "run_id": run_id,
        "topics": 8,
        "topic_assignments": 640,
    }
    assert conn.commits == 1 and conn.rollbacks == 0 and conn.autocommit is True
    update = next((params for query, params in cursor.calls if query.startswith("UPDATE model_runs")), None)
    assert update is not None and update[1] == run_id
    assert json.loads(update[0])["demo_baseline"] is True


def test_operator_prepare_requires_exact_confirmation_before_aws(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "prepare_demo.py"),
            "prepare",
            "--stack",
            "compass-demo",
            "--receipt",
            str(receipt_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    receipt = json.loads(receipt_path.read_text())
    assert receipt["failed_stage"] == "confirmation"
    assert receipt["ready"] is False


def test_stack_discovery_uses_named_outputs_not_truncated_resource_listing(monkeypatch):
    calls = []

    def aws(args, **kwargs):
        calls.append((args, kwargs))
        return {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "RawBucketName", "OutputValue": "hidden-bucket"},
                        {"OutputKey": "UserPoolId", "OutputValue": "pool"},
                        {"OutputKey": "MigratorFunctionName", "OutputValue": "migrator"},
                        {"OutputKey": "AnalyticsFunctionName", "OutputValue": "analytics"},
                    ]
                }
            ]
        }

    monkeypatch.setattr(prepare_script, "_aws", aws)
    resources = prepare_script._stack_resources("compass-demo", "us-east-1")
    assert resources == {
        "RawBucket": "hidden-bucket",
        "UserPool": "pool",
        "MigratorFunction": "migrator",
        "AnalyticsFunction": "analytics",
    }
    assert calls[0][0][:2] == ["cloudformation", "describe-stacks"]
    assert "describe-stack-resources" not in calls[0][0]


def test_infrastructure_routes_only_the_live_drop_prefix_and_redacts_state_data():
    template = (ROOT / "template.yaml").read_text()
    state_machine = (ROOT / "statemachines" / "intake.asl.yaml").read_text()
    assert "- prefix: drops/" in template
    assert "IncludeExecutionData: false" in template
    assert "demo-stage/*" in template
    assert "bucket.$: $.bucket" not in state_machine
    assert "key.$: $.key" not in state_machine
