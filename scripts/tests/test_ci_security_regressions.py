from __future__ import annotations

import subprocess

import pytest

from scripts import check_api_cors, status_dashboard


def test_cors_probe_requires_an_https_api_base_url():
    assert (
        check_api_cors.validated_api_base_url("https://api.example.test/prod/")
        == "https://api.example.test/prod"
    )

    with pytest.raises(ValueError, match="https URL"):
        check_api_cors.validated_api_base_url("file:///tmp/local-api")


def test_status_dashboard_does_not_execute_modified_status_command(monkeypatch):
    calls: list[tuple[object, ...]] = []

    def record_run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(status_dashboard.subprocess, "run", record_run)

    result = status_dashboard.run_checks(
        [
            {
                "name": "Repository content policy",
                "command": "python3 scripts/check_no_em_dash.py; touch /tmp/not-allowed",
            }
        ]
    )

    assert calls == []
    assert result == [
        (
            "Repository content policy",
            "not executable: command is not an approved dashboard check",
            False,
        )
    ]
