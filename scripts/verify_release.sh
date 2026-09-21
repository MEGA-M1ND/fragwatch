#!/usr/bin/env bash
# One offline command that re-verifies the archived CloudFormation templates, regenerates the
# nine-campaign table, replays the measurement-bug reproductions, and checks every headline against
# regenerated values.
#
# Needs: python3 (3.11+) and git. No third-party packages, no API key, no Docker, no model calls.
# Any missing artefact or disagreeing headline exits non-zero.
set -euo pipefail

PY="${PYTHON:-python3}"
cd "$(dirname "$0")/.."

echo "=============================================================="
echo " fragwatch release verification (offline)"
echo " python: $($PY --version 2>&1) | repo: $(git rev-parse --short HEAD)"
echo "=============================================================="

echo
echo "### 1/4  Archived templates re-verify to the published classifications"
echo
"$PY" src/fragwatch/check_templates.py

echo
echo "### 2/4  Nine-campaign results table"
echo
"$PY" src/fragwatch/pilot_report.py

echo
echo "### 3/4  Measurement-bug reproductions (archived replay)"
echo
"$PY" src/fragwatch/repro_bugs.py

echo
echo "### 4/4  Generated sections match the canonical summary"
echo
"$PY" src/fragwatch/sections.py --check

echo
echo "All four stages passed."
