#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ARTIFACT_DIR=".verification-artifacts"
mkdir -p "$ARTIFACT_DIR"
export PYTHONPATH="$ROOT:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -m compileall -q src tests scripts/operate.py

for pass in 1 2; do
  python -m unittest discover -s tests -v 2>&1 | tee "$ARTIFACT_DIR/unittest-pass-${pass}.log"
done

for pass in 1 2; do
  python scripts/operate.py | tee "$ARTIFACT_DIR/operate-pass-${pass}.json"
done

python - <<'PY'
import hashlib
import json
import os
import re
from pathlib import Path

artifact_dir = Path('.verification-artifacts')

test_counts = []
for idx in (1, 2):
    text = (artifact_dir / f'unittest-pass-{idx}.log').read_text(encoding='utf-8')
    match = re.search(r'^Ran ([1-9][0-9]*) tests? in ', text, flags=re.MULTILINE)
    if match is None:
        raise SystemExit(f'unittest pass {idx} did not prove a non-empty test run')
    test_counts.append(int(match.group(1)))
if test_counts[0] != test_counts[1]:
    raise SystemExit('dual unittest runs executed different test counts')

outputs = []
for idx in (1, 2):
    path = artifact_dir / f'operate-pass-{idx}.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('ok') is not True:
        raise SystemExit(f'operate pass {idx} did not report ok=true')
    smoke = payload.get('smoke') or {}
    if smoke.get('invoked') is not True or smoke.get('content_checked') is not True:
        raise SystemExit(f'operate pass {idx} did not exercise a content-checked mechanism')
    outputs.append(payload)

if outputs[0] != outputs[1]:
    raise SystemExit('dual operate runs were not deterministic')

summary = {
    'schema': 'glaciereq.ci-verification.v1',
    'repository': os.environ.get('GITHUB_REPOSITORY', 'GlacierEQ/spacex-ground-network'),
    'head_ref': os.environ.get('GITHUB_HEAD_REF') or os.environ.get('GITHUB_REF_NAME'),
    'github_sha': os.environ.get('GITHUB_SHA'),
    'compileall': True,
    'unittest_runs': 2,
    'unittest_count_each_run': test_counts[0],
    'operate_runs': 2,
    'dual_run_equal': True,
    'operate_sha256': hashlib.sha256(
        json.dumps(outputs[0], sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest(),
    'result': 'PASS',
}
(artifact_dir / 'verification-summary.json').write_text(
    json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8'
)
print(json.dumps(summary, sort_keys=True))
PY
