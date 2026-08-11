"""Negative security tests for export approvals and database grants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import os
import sys
import unittest


ROOT = Path(__file__).resolve().parents[4]
EXPORT_DIR = ROOT / "src" / "functions" / "export"
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
sys.path.insert(0, str(EXPORT_DIR))

os.environ.setdefault("DB_HOST", "fake")
os.environ.setdefault("DB_NAME", "fake")
os.environ.setdefault("DB_SECRET_ARN", "fake")

APP_SPEC = importlib.util.spec_from_file_location(
    "compass_export_app",
    EXPORT_DIR / "app.py",
)
assert APP_SPEC and APP_SPEC.loader
export_app = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = export_app
APP_SPEC.loader.exec_module(export_app)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
SECRET = "A" * 43
TOKEN = f"apr-42.{SECRET}"


class ApprovalCursor:
    def __init__(self, conn):
        self.conn = conn
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        text = " ".join(str(query).split())
        self.conn.executed.append((text, params))
        if text.startswith("SELECT id, subject_type"):
            row = self.conn.row
            if row is None:
                self.result = None
                return
            active = bool(row["expires_at"] and row["expires_at"] > NOW)
            self.result = (
                row["id"],
                row["subject_type"],
                row["subject_id"],
                row["state"],
                row["requested_by"],
                row["decided_by"],
                row["decided_at"],
                row["expires_at"],
                row["consumed_at"],
                row["consumed_by"],
                row["capability_hash"],
                active,
            )
            return
        if text.startswith("UPDATE approvals SET consumed_at"):
            row = self.conn.row
            if (
                row is not None
                and self.conn.allow_consume
                and row["state"] == "approved"
                and row["consumed_at"] is None
                and row["expires_at"] is not None
                and row["expires_at"] > NOW
                and row["capability_hash"] == params[2]
            ):
                row["consumed_at"] = NOW
                row["consumed_by"] = params[0]
                self.result = (NOW,)
            else:
                self.result = None

    def fetchone(self):
        return self.result


class ApprovalConn:
    def __init__(
        self,
        *,
        subject_id="exp-0123456789abcdef",
        subject_type="export",
        state="approved",
        expires_at=None,
        consumed_at=None,
        allow_consume=True,
        capability_hash=export_app.capability_digest(SECRET),
    ):
        self.row = {
            "id": 42,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "state": state,
            "requested_by": "requester",
            "decided_by": "reviewer",
            "decided_at": NOW - timedelta(minutes=5),
            "expires_at": expires_at or NOW + timedelta(minutes=55),
            "consumed_at": consumed_at,
            "consumed_by": None,
            "capability_hash": capability_hash,
        }
        self.allow_consume = allow_consume
        self.executed = []

    def cursor(self):
        return ApprovalCursor(self)


class ExportApprovalTests(unittest.TestCase):
    fingerprint = "exp-0123456789abcdef"

    def test_limit_is_part_of_the_exact_request_fingerprint(self):
        base = export_app.filter_fingerprint(
            "Code-30",
            "csv",
            ["grant_no", "title"],
            {"program_area": "Hypersonics"},
        )
        limited = export_app.filter_fingerprint(
            "Code-30",
            "csv",
            ["grant_no", "title"],
            {"program_area": "Hypersonics", "limit": 5},
        )
        other_limit = export_app.filter_fingerprint(
            "Code-30",
            "csv",
            ["grant_no", "title"],
            {"program_area": "Hypersonics", "limit": 6},
        )
        self.assertNotEqual(base, limited)
        self.assertNotEqual(limited, other_limit)

    def test_exact_unexpired_token_is_consumed_once(self):
        conn = ApprovalConn()
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
            actor="power.user",
        )
        self.assertTrue(ok)
        self.assertEqual(detail["binding"], "exact-request")
        self.assertEqual(detail["consumed_by"], "power.user")
        self.assertEqual(conn.row["consumed_at"], NOW)

        second_ok, second_detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
            actor="power.user",
        )
        self.assertFalse(second_ok)
        self.assertIn("already consumed", second_detail["reason"])

    def test_legacy_unbound_subject_is_rejected(self):
        conn = ApprovalConn(subject_id="legacy-request")
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertEqual(detail["binding"], "rejected")
        self.assertIsNone(conn.row["consumed_at"])

    def test_different_export_fingerprint_is_rejected(self):
        conn = ApprovalConn(subject_id="exp-aaaaaaaaaaaaaaaa")
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("exact export fingerprint", detail["reason"])

    def test_expired_token_is_rejected_without_consumption(self):
        conn = ApprovalConn(expires_at=NOW - timedelta(seconds=1))
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("expired", detail["reason"])
        self.assertIsNone(conn.row["consumed_at"])

    def test_non_export_and_non_approved_records_are_rejected(self):
        wrong_type = ApprovalConn(subject_type="analytics")
        ok, detail = export_app.check_approval(
            wrong_type,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("not 'export'", detail["reason"])

        pending = ApprovalConn(state="pending")
        ok, detail = export_app.check_approval(
            pending,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("not 'approved'", detail["reason"])

    def test_conditional_consume_failure_fails_closed(self):
        conn = ApprovalConn(allow_consume=False)
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("used by another request", detail["reason"])

    def test_malformed_token_never_queries_database(self):
        conn = ApprovalConn()
        ok, detail = export_app.check_approval(
            conn,
            "not-a-token",
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("malformed", detail["reason"])
        self.assertEqual(conn.executed, [])

    def test_legacy_predictable_token_fails_closed_before_database_access(self):
        conn = ApprovalConn()
        ok, detail = export_app.check_approval(
            conn,
            "apr-42",
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertIn("legacy", detail["reason"])
        self.assertEqual(conn.executed, [])

    def test_wrong_opaque_secret_is_rejected_without_consumption(self):
        conn = ApprovalConn()
        bad_token = f"apr-42.{'B' * 43}"
        ok, detail = export_app.check_approval(
            conn,
            bad_token,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertEqual(detail["reason"], "approval_token secret rejected")
        self.assertIsNone(conn.row["consumed_at"])
        self.assertNotIn(SECRET, str(detail))

    def test_approved_record_without_a_hash_cannot_authorize_export(self):
        conn = ApprovalConn(capability_hash=None)
        ok, detail = export_app.check_approval(
            conn,
            TOKEN,
            self.fingerprint,
        )
        self.assertFalse(ok)
        self.assertEqual(detail["reason"], "approval_token secret rejected")
        self.assertIsNone(conn.row["consumed_at"])


class MigrationSecurityContractTests(unittest.TestCase):
    def test_forward_migration_enforces_negative_controls(self):
        root = Path(__file__).resolve().parents[4]
        canonical_003 = root / "db/migrations/003_security_hardening.sql"
        staged_003 = (
            root
            / "src/functions/migrator/migrations/003_security_hardening.sql"
        )
        canonical_004 = root / "db/migrations/004_opaque_approval_capability.sql"
        staged_004 = (
            root
            / "src/functions/migrator/migrations/004_opaque_approval_capability.sql"
        )
        sql = canonical_003.read_text(encoding="utf-8")
        capability_sql = canonical_004.read_text(encoding="utf-8")
        self.assertEqual(sql, staged_003.read_text(encoding="utf-8"))
        self.assertEqual(
            capability_sql,
            staged_004.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "REVOKE SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER",
            sql,
        )
        self.assertIn("GRANT UPDATE (source_file, ingested_at, raw_jsonb)", sql)
        self.assertIn(
            "GRANT UPDATE (batch_id, passed_rows, failed_rows, score, details_jsonb, created_at)",
            sql,
        )
        self.assertNotIn("capability_hash", sql)
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS capability_hash TEXT",
            capability_sql,
        )
        self.assertIn(
            "GRANT UPDATE (capability_hash)",
            capability_sql,
        )
        self.assertIn("REVOKE ALL ON audit_log FROM compass_app", sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON audit_log", sql)
        self.assertIn(
            "current_setting('compass.org_unit', true) = 'ONR-Corporate'",
            sql,
        )
        self.assertIn("REVOKE SELECT ON grants_curated FROM compass_app", sql)
        self.assertNotIn("GRANT SELECT, INSERT, UPDATE ON ALL TABLES", sql)


class OpenApiApprovalContractTests(unittest.TestCase):
    def test_opaque_token_and_top_level_columns_are_documented(self):
        document = export_app.build_openapi()
        schemas = document["components"]["schemas"]
        approval_token = schemas["ApprovalResponse"]["properties"]["approval_token"]
        export_token = schemas["ExportRequest"]["properties"]["approval_token"]

        self.assertNotIn("pattern", approval_token)
        self.assertNotIn("pattern", export_token)
        self.assertIn("Opaque", approval_token["description"])
        self.assertIn("columns", schemas["ExportRequest"]["properties"])
        self.assertNotIn(
            "columns",
            schemas["ExportRequest"]["properties"]["filters"]["properties"],
        )
        self.assertIn("get", document["paths"]["/approvals"])
        dashboard_params = {
            item["name"] for item in document["paths"]["/dashboard"]["get"]["parameters"]
        }
        self.assertEqual(
            dashboard_params,
            {"program_area", "fiscal_year", "org_unit", "q"},
        )


if __name__ == "__main__":
    unittest.main()
