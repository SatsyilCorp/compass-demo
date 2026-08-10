"""Offline smoke test for the compass_common layer.

Runs with NO network, AWS, DB, psycopg2, or boto3: every AWS/DB touchpoint is
either lazily imported (so import succeeds without it) or exercised through an
injected fake. Asserts the contract-facing behavior of all five modules.

    make -C src/common smoke      # or: PYTHONPATH=src/common/python python3 src/common/tests/smoke.py
"""
import io
import json
import os

# Env must exist before importing config-driven modules.
os.environ.setdefault("DB_HOST", "fake-host")
os.environ.setdefault("DB_NAME", "fake-db")
os.environ.setdefault("DB_SECRET_ARN", "arn:aws:secretsmanager:fake")
os.environ.pop("DB_SCHEMA", None)
os.environ.pop("EXPORT_MAX_ROWS", None)

from compass_common import audit, config, db, http, llm  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((str(sql), params))

    def fetchone(self):
        return (4242,)


class FakeConn:
    def __init__(self):
        self.executed = []
        self.autocommit = True
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


class FakeBedrock:
    """Minimal stand-in for a bedrock-runtime client."""

    def __init__(self):
        self.calls = []

    def converse(self, **kw):
        self.calls.append(("converse", kw))
        return {
            "output": {"message": {"content": [{"text": "topic drift up in FY24"}]}},
            "usage": {"inputTokens": 12, "outputTokens": 7, "totalTokens": 19},
        }

    def invoke_model(self, **kw):
        self.calls.append(("invoke_model", kw))
        vec = [0.01] * config.EMBED_DIMENSIONS_DEFAULT
        return {"body": io.BytesIO(json.dumps({"embedding": vec}).encode())}


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_config_defaults():
    assert config.db_schema() == "compass"
    assert config.bedrock_chat_model() == "amazon.nova-lite-v1:0"
    assert config.bedrock_embed_model() == "amazon.titan-embed-text-v2:0"
    assert config.export_max_rows() == 5000
    cfg = config.load_config()
    assert cfg.db_schema == "compass" and cfg.export_max_rows == 5000
    assert config.APP_ROLE == "compass_app"
    assert config.ORG_SETTING == "compass.org_unit"


def test_http_responses():
    r = http.json_response(200, {"hello": "world"})
    assert r["statusCode"] == 200
    assert r["headers"]["Content-Type"] == "application/json"
    assert json.loads(r["body"]) == {"hello": "world"}

    e = http.error_response(403, "nope", detail="x")
    assert e["statusCode"] == 403 and json.loads(e["body"])["error"] == "nope"

    guard = http.approval_required("approval required", requested_rows=9000)
    assert guard["statusCode"] == 428
    assert json.loads(guard["body"])["requested_rows"] == 9000


def test_get_claims_lambda_authorizer():
    event = {
        "requestContext": {
            "http": {"method": "GET", "path": "/dashboard"},
            "authorizer": {
                "lambda": {
                    "sub": "u-1",
                    "username": "viewer1",
                    "role": "viewer",
                    "org_unit": "Code-30",
                    "groups": "viewer",
                }
            },
        }
    }
    c = http.get_claims(event)
    assert c.role == "viewer" and c.org_unit == "Code-30"
    assert c.is_authenticated and not c.is_corporate
    assert c.groups == ["viewer"]
    assert http.get_method(event) == "GET" and http.get_path(event) == "/dashboard"

    corp = http.get_claims(
        {"requestContext": {"authorizer": {"jwt": {"claims": {
            "role": "poweruser", "org_unit": "ONR-Corporate"}}}}}
    )
    assert corp.is_corporate

    anon = http.get_claims({})
    assert not anon.is_authenticated


def test_parse_body():
    assert http.parse_body({"body": None}) == {}
    assert http.parse_body({"body": '{"a": 1}'}) == {"a": 1}
    raised = False
    try:
        http.parse_body({"body": "not json"})
    except ValueError:
        raised = True
    assert raised, "malformed body must raise ValueError"


def test_set_org_sets_local_and_commits():
    conn = FakeConn()
    with db.set_org(conn, "Code-30") as c:
        assert c is conn
        assert conn.autocommit is False, "must open a real transaction"
    assert conn.committed == 1
    set_locals = [q for (q, _) in conn.executed if "SET LOCAL" in q]
    assert set_locals, "must issue SET LOCAL"
    assert set_locals[0] == "SET LOCAL compass.org_unit = %s"
    assert conn.executed[0][1] == ("Code-30",)
    assert conn.autocommit is True, "must restore prior autocommit"


def test_set_org_rejects_empty_and_rolls_back_on_error():
    conn = FakeConn()
    for bad in ("", "   ", None):
        raised = False
        try:
            with db.set_org(conn, bad):
                pass
        except ValueError:
            raised = True
        assert raised, f"set_org must reject org_unit={bad!r}"

    conn2 = FakeConn()
    raised = False
    try:
        with db.set_org(conn2, "Code-30"):
            raise RuntimeError("boom")
    except RuntimeError:
        raised = True
    assert raised and conn2.rolled_back == 1 and conn2.committed == 0


def test_llm_converse_and_embed_offline():
    fake = FakeBedrock()
    out = llm.converse(system="be terse", user="summarize", client_factory=lambda: fake)
    assert out["text"] == "topic drift up in FY24"
    assert out["model_id"] == "amazon.nova-lite-v1:0"
    assert out["usage"]["totalTokens"] == 19

    vec = llm.embed("solid-state sonar arrays", client_factory=lambda: fake)
    assert len(vec) == config.EMBED_DIMENSIONS_DEFAULT == 1024

    raised = False
    try:
        llm.embed("   ", client_factory=lambda: fake)
    except ValueError:
        raised = True
    assert raised, "embed must reject empty text"


def test_write_audit_inserts_and_returns_id():
    conn = FakeConn()
    new_id = audit.write_audit(
        conn, actor="viewer1", action="export_blocked",
        resource="grants_curated", detail={"requested_rows": 9000},
    )
    assert new_id == 4242
    inserts = [(q, p) for (q, p) in conn.executed if "INSERT INTO audit_log" in q]
    assert inserts, "must insert into audit_log"
    q, params = inserts[0]
    assert "%s::jsonb" in q, "detail must be cast to jsonb"
    assert params[0] == "viewer1" and params[1] == "export_blocked"
    assert json.loads(params[3]) == {"requested_rows": 9000}


def test_modules_import_clean():
    # The whole point: importable with no psycopg2 / boto3 / network present.
    for name in ("config", "db", "llm", "http", "audit"):
        assert hasattr(__import__("compass_common", fromlist=[name]), name)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK compass_common smoke passed ({len(tests)} tests, fully offline)")
