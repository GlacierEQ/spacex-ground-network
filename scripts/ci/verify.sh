#!/usr/bin/env bash
set -euo pipefail

python -m pip install --disable-pip-version-check ruff pytest
[[ -f requirements.txt ]] && python -m pip install -r requirements.txt
[[ -f requirements-dev.txt ]] && python -m pip install -r requirements-dev.txt

python -m ruff check --select E9,F63,F7,F82 .
python -m compileall -q src tests
python -m pytest -x -q

install -d -m 700 .verification-artifacts
python - <<'PY'
import json
import os
from pathlib import Path

receipt = {
    "schema": "glaciereq.repository-verification.v1",
    "repository": os.environ["GITHUB_REPOSITORY"],
    "head_sha": os.environ["GITHUB_SHA"],
    "verification": {
        "critical_lint": "PASS",
        "compileall": "PASS",
        "pytest": "PASS",
    },
    "scope": "repository-native-source-and-tests",
}
Path(".verification-artifacts/verification.json").write_text(
    json.dumps(receipt, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
PY
