#!/usr/bin/env bash
# One offline command that regenerates the nine-campaign table, replays the measurement-bug
# reproductions, and checks every headline against regenerated values.
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
echo "### 1/3  Nine-campaign results table"
echo
"$PY" src/fragwatch/pilot_report.py

echo
echo "### 2/3  Measurement-bug reproductions (archived replay)"
echo
"$PY" src/fragwatch/repro_bugs.py

echo
echo "### 3/3  Headline consistency"
echo
"$PY" src/fragwatch/check_headlines.py

echo
echo "All three stages passed."
