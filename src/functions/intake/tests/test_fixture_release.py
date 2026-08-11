"""Fixed synthetic fixture release contract for the live ingest UI."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
FUNCTION_DIR = ROOT / "src" / "functions" / "intake"
COMMON_DIR = ROOT / "src" / "common" / "python"
for path in (str(COMMON_DIR), str(FUNCTION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

SPEC = importlib.util.spec_from_file_location(
    "compass_intake_fixture_release_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class Cursor:
    def __init__(self, approved_digest):
        self.approved_digest = approved_digest
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.query = str(query)
        assert params == ("drop_good_sha256",)

    def fetchone(self):
        return (self.approved_digest,)


class Connection:
    def __init__(self, approved_digest):
        self.cursor_instance = Cursor(approved_digest)

    def cursor(self):
        return self.cursor_instance


class PreconditionFailed(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class S3:
    def __init__(self, body, *, duplicate=False):
        self.body = body
        self.duplicate = duplicate
        self.put_calls = []

    def get_object(self, *, Bucket, Key):
        assert Key == "demo-stage/drops/drop_good.fixture"
        digest = hashlib.sha256(self.body).hexdigest()
        return {
            "Body": io.BytesIO(self.body),
            "Metadata": {
                "fixture-sha256": digest,
                "synthetic-only": "true",
            },
        }

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self.duplicate:
            raise PreconditionFailed()
        return {"ETag": "redacted"}


def _install_db(monkeypatch, digest):
    conn = Connection(digest)
    monkeypatch.setattr(app.db, "get_conn", lambda: conn)

    @contextmanager
    def set_org(got, org):
        assert got is conn
        assert org == "ONR-Corporate"
        yield got

    monkeypatch.setattr(app.db, "set_org", set_org)
    monkeypatch.setattr(app.audit, "write_audit", lambda *_args, **_kwargs: None)
    return conn


def _identity():
    return app.Identity(
        "poweruser",
        "ONR-Corporate",
        "poweruser@compass.demo",
        ["compass-poweruser"],
    )


def _good_fixture():
    return (ROOT / "seed" / "drops" / "drop_good.json").read_bytes()


def test_release_validates_immutable_receipt_and_relies_on_object_event(monkeypatch):
    body = _good_fixture()
    digest = hashlib.sha256(body).hexdigest()
    fake_s3 = S3(body)
    _install_db(monkeypatch, digest)
    monkeypatch.setattr(app.pipeline, "_s3", lambda: fake_s3)
    monkeypatch.setattr(
        app,
        "_start_execution",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("fixture release must not start a duplicate workflow")
        ),
    )

    response = app._release_prepared_fixture(
        _identity(),
        "physical-name-hidden",
        "good",
        "2026-08-10T12:00:00+00:00",
    )

    assert response["statusCode"] == 202
    payload = json.loads(response["body"])
    assert payload["trigger"] == "s3-object-created"
    assert payload["batch_id"] == "drop-good-2026-08"
    assert "physical-name-hidden" not in response["body"]
    assert len(fake_s3.put_calls) == 1
    put = fake_s3.put_calls[0]
    assert put["Key"] == "drops/drop_good.json"
    assert put["IfNoneMatch"] == "*"
    assert put["Body"] == body


def test_release_rejects_bytes_not_bound_to_latest_prepare_receipt(monkeypatch):
    body = _good_fixture()
    fake_s3 = S3(body)
    _install_db(monkeypatch, "0" * 64)
    monkeypatch.setattr(app.pipeline, "_s3", lambda: fake_s3)

    response = app._release_prepared_fixture(
        _identity(), "physical-name-hidden", "good", "now"
    )

    assert response["statusCode"] == 409
    assert fake_s3.put_calls == []


def test_release_is_one_shot_under_concurrency(monkeypatch):
    body = _good_fixture()
    digest = hashlib.sha256(body).hexdigest()
    fake_s3 = S3(body, duplicate=True)
    _install_db(monkeypatch, digest)
    monkeypatch.setattr(app.pipeline, "_s3", lambda: fake_s3)

    response = app._release_prepared_fixture(
        _identity(), "physical-name-hidden", "good", "now"
    )

    assert response["statusCode"] == 409
    assert "already released" in response["body"]


def test_fixture_action_remains_poweruser_protected(monkeypatch):
    called = []
    monkeypatch.setattr(
        app,
        "_release_prepared_fixture",
        lambda identity, *_args: called.append(identity.role) or {"statusCode": 202},
    )
    monkeypatch.setenv("RAW_BUCKET", "physical-name-hidden")

    poweruser = {
        "requestContext": {
            "http": {"method": "POST", "path": "/ingest/simulate"},
            "authorizer": {
                "lambda": {
                    "sub": "demo",
                    "username": "poweruser@compass.demo",
                    "role": "poweruser",
                    "org_unit": "ONR-Corporate",
                    "groups": '["compass-poweruser"]',
                }
            },
        },
        "routeKey": "POST /ingest/simulate",
        "body": json.dumps({"fixture": "good"}),
    }
    assert app.handler(poweruser, None)["statusCode"] == 202
    assert called == ["poweruser"]

    viewer = json.loads(json.dumps(poweruser))
    viewer["requestContext"]["authorizer"]["lambda"].update(
        {
            "username": "viewer@compass.demo",
            "role": "viewer",
            "org_unit": "Code-30",
            "groups": '["compass-viewer"]',
        }
    )
    assert app.handler(viewer, None)["statusCode"] == 403
    assert called == ["poweruser"]
