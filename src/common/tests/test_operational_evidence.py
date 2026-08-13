from __future__ import annotations

from compass_common import operational_evidence


class Table:
    def __init__(self):
        self.items = []
        self.keys = set()

    def put_item(self, *, Item, ConditionExpression=None):
        key = (Item["pk"], Item["sk"])
        if ConditionExpression and key in self.keys:
            raise ConditionalCheckFailedException()
        self.keys.add(key)
        self.items.append(Item)


class ConditionalCheckFailedException(RuntimeError):
    pass


class Sns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


def test_stage_receipt_is_digest_bound_and_redacted(monkeypatch):
    table = Table()
    monkeypatch.setattr(operational_evidence, "_TABLE", table)
    monkeypatch.setenv("OPERATIONS_TABLE", "test")
    written = operational_evidence.record_stage(
        run_id="doc-safe",
        run_kind="document-intake",
        sequence=2,
        stage_id="bronze",
        label="Bronze retained",
        status="completed",
        source="document-lake://documents/incoming/doc-safe/report.txt",
        source_sha256="a" * 64,
        detail={"record_count": 4, "secret": "must-not-leak"},
        occurred_at="2026-08-12T12:00:00+00:00",
    )
    assert written is True
    item = table.items[0]
    assert item["pk"] == "RUN#doc-safe"
    assert item["sk"] == "STAGE#002#bronze"
    assert len(item["receipt_sha256"]) == 64
    assert item["detail"] == {"record_count": 4}


def test_signal_persists_and_publishes_safe_message(monkeypatch):
    table, sns = Table(), Sns()
    monkeypatch.setattr(operational_evidence, "_TABLE", table)
    monkeypatch.setattr(operational_evidence, "_SNS", sns)
    monkeypatch.setenv("OPERATIONS_TABLE", "test")
    monkeypatch.setenv("OPERATIONS_TOPIC_ARN", "arn:aws:sns:us-east-1:111122223333:test")
    event_id = operational_evidence.record_signal(
        category="quality",
        severity="high",
        title="Quality gate blocked publication",
        message="3 records were quarantined",
        run_id="run-safe",
        detail={"failed_records": 3, "account_id": "must-not-leak"},
        occurred_at="2026-08-12T12:00:00+00:00",
    )
    assert event_id and event_id.startswith("sig-")
    assert len(sns.messages) == 1
    assert table.items[-1]["delivery"]["status"] == "published"
    assert "must-not-leak" not in str(table.items)


def test_missing_table_is_a_fail_soft_noop(monkeypatch):
    monkeypatch.delenv("OPERATIONS_TABLE", raising=False)
    monkeypatch.setattr(operational_evidence, "_TABLE", None)
    assert operational_evidence.record_stage(
        run_id="run",
        run_kind="ingest",
        sequence=1,
        stage_id="received",
        label="Received",
        status="completed",
    ) is False


def test_duplicate_signal_does_not_reopen_or_republish(monkeypatch):
    table, sns = Table(), Sns()
    monkeypatch.setattr(operational_evidence, "_TABLE", table)
    monkeypatch.setattr(operational_evidence, "_SNS", sns)
    monkeypatch.setenv("OPERATIONS_TABLE", "test")
    monkeypatch.setenv("OPERATIONS_TOPIC_ARN", "arn:aws:sns:us-east-1:111122223333:test")
    first = operational_evidence.record_signal(
        category="model-execution",
        severity="info",
        title="Model run completed",
        message="A retained run completed.",
        run_id="run-idempotent",
        occurred_at="2026-08-12T12:00:00+00:00",
    )
    writes_after_first = len(table.items)
    second = operational_evidence.record_signal(
        category="model-execution",
        severity="info",
        title="Model run completed",
        message="A retained run completed.",
        run_id="run-idempotent",
        occurred_at="2026-08-12T12:05:00+00:00",
    )
    assert second == first
    assert len(table.items) == writes_after_first
    assert len(sns.messages) == 1
