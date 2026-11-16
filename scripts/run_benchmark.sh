#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source infrastructure/runtime.sh
bash scripts/start_cluster.sh
"$SPARK_HOME/bin/spark-submit" --master spark://127.0.0.1:17077 --driver-memory 1g --executor-memory 1g --total-executor-cores 2 --conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 --conf spark.ui.port=14040 spark_jobs/benchmark.py 2>&1 | tee logs/benchmark.log
