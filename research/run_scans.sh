#!/usr/bin/env bash
# Reproduce the cross-script scan inside the sandbox image (Chromium + Noto fonts for all four scripts).
#   bash research/run_scans.sh            (on the Vultr VM, from the repo root)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p research/results
for s in ${SCRIPTS:-lao thai khmer myanmar}; do
  docker run --rm --shm-size=1g -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/w" -w /w --entrypoint python3 \
    glyphsweep-sandbox:latest research/scan.py --script "$s" --sites "research/sites_$s.csv" \
    --out "research/results/scan_$s.jsonl" --shots "research/results/shots_$s" --workers "${WORKERS:-2}"
done
python3 research/compare.py
