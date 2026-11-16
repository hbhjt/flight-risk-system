#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"
source infrastructure/runtime.sh
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
PHASE="${1:-prepare}"
case "$PHASE" in prepare|pilot|formal|export) ;; *) echo 'Expected prepare/pilot/formal/export'; exit 1;; esac
mkdir -p artifacts/ml logs
"$SPARK_HOME/bin/spark-submit" --master spark://127.0.0.1:17077 \
  --driver-memory 1g --executor-memory 1g --total-executor-cores 2 \
  --conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 \
  --conf spark.ui.port=14040 --conf spark.eventLog.enabled=true \
  --conf "spark.eventLog.dir=file://$FLIGHT_RUNTIME/spark-events" \
  ml/run_experiment.py "$PHASE" 2>&1 | tee "logs/ml-$PHASE.log"
