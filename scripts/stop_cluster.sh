#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT/infrastructure/runtime.sh"
for role in worker master; do
  pidfile="$SPARK_PID_DIR/$role.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    # Confirm ownership by command line before signalling a saved PID.
    if ps -p "$pid" -o args= | grep -q 'org.apache.spark.deploy'; then
      kill "$pid"
    fi
    rm -f "$pidfile"
  fi
done
hdfs --daemon stop datanode
hdfs --daemon stop namenode
