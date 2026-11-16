#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"
source infrastructure/runtime.sh
bash scripts/start_cluster.sh
mkdir -p artifacts/months
for month in 2024-01 2024-02 2024-03 2024-04 2024-05 2024-06; do
  if [ ! -f "artifacts/months/$month.sqlite" ]; then
    bash scripts/run_etl.sh "$month" "artifacts/months/$month.sqlite"
  fi
done
python scripts/merge_months.py
