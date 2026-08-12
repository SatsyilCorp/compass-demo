from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_build_prefers_the_deployed_custom_domain_callback(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    fake_bin = tmp_path / "bin"
    capture = tmp_path / "frontend-env.txt"
    (repository / "scripts").mkdir(parents=True)
    (repository / "frontend").mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "build-frontend.sh",
        repository / "scripts" / "build-frontend.sh",
    )
    _make_executable(
        fake_bin / "aws",
        """#!/usr/bin/env python3
import sys

query = sys.argv[sys.argv.index("--query") + 1]
outputs = {
    "ApiBaseUrl": "https://api.example/prod",
    "CognitoDomain": "compass.auth.example",
    "UserPoolId": "us-east-1_example",
    "WebClientId": "client-example",
    "CloudFrontDomain": "distribution.cloudfront.net",
    "CustomDomainUrl": "https://compass.example",
}
for key, value in outputs.items():
    if f"OutputKey==`{key}`" in query:
        print(value)
        raise SystemExit(0)
raise SystemExit(f"unexpected query: {query}")
""",
    )
    _make_executable(
        fake_bin / "corepack",
        """#!/usr/bin/env sh
set -eu
printf '%s\n' "$NEXT_PUBLIC_COGNITO_REDIRECT_URI" > "$BUILD_ENV_CAPTURE"
printf '%s\n' "$NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI" >> "$BUILD_ENV_CAPTURE"
""",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "BUILD_ENV_CAPTURE": str(capture),
        }
    )

    result = subprocess.run(
        [str(repository / "scripts" / "build-frontend.sh")],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "https://compass.example/login/",
        "https://compass.example/login/",
    ]
