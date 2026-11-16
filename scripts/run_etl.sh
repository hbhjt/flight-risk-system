#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT/infrastructure/runtime.sh"
cd "$PROJECT"
MONTH="${1:-2024-01}"
[[ "$MONTH" =~ ^2024-0[1-6]$ ]] || { echo 'Month must be 2024-01 through 2024-06'; exit 1; }
mapfile -t FILES < <(find "data/raw/csv/$MONTH" -maxdepth 1 -type f -name '*.csv')
[ "${#FILES[@]}" = 1 ] || { echo 'Expected one official monthly CSV'; exit 1; }
mkdir -p artifacts logs
hdfs dfs -mkdir -p "/flight-risk/raw/$MONTH"
hdfs dfs -put -f "${FILES[0]}" "/flight-risk/raw/$MONTH/flights.csv"
"$SPARK_HOME/bin/spark-submit" --master spark://127.0.0.1:17077 \
  --driver-memory 1g --executor-memory 1g --total-executor-cores 2 \
  --conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 \
  --conf spark.ui.port=14040 --conf spark.eventLog.enabled=true \
  --conf "spark.eventLog.dir=file://$FLIGHT_RUNTIME/spark-events" \
  spark_jobs/etl.py --input "hdfs://127.0.0.1:19000/flight-risk/raw/$MONTH/flights.csv" \
  --output "hdfs://127.0.0.1:19000/flight-risk/runs/$MONTH" \
  --database artifacts/flight.sqlite --report "artifacts/quality-$MONTH.json" 2>&1 | tee "logs/etl-$MONTH.log"
hdfs dfs -ls -R "/flight-risk/runs/$MONTH" > "artifacts/hdfs-$MONTH.txt"
