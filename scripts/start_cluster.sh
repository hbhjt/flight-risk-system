#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT/infrastructure/runtime.sh"
test -f "$FLIGHT_RUNTIME/hdfs/name/current/VERSION"
for role in namenode datanode; do
  if ! hdfs --daemon status "$role" > /dev/null 2>&1; then
    # Detach from the launching WSL command so closing it cannot SIGHUP HDFS.
    setsid hdfs --daemon start "$role"
  fi
done
export SPARK_MASTER_HOST=127.0.0.1
export SPARK_MASTER_PORT=17077
export SPARK_MASTER_WEBUI_PORT=18080
export SPARK_DAEMON_MEMORY=256m
export SPARK_WORKER_CORES=2
export SPARK_WORKER_MEMORY=2g
export SPARK_WORKER_WEBUI_PORT=18081
# The PyPI distribution includes spark-class but does not include sbin launchers.
spark_running() {
  local role="$1" expected="$2" pidfile="$SPARK_PID_DIR/$1.pid"
  [ -f "$pidfile" ] || return 1
  local pid
  pid="$(cat "$pidfile")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  ps -p "$pid" -o args= 2>/dev/null | grep -q "$expected"
}
if ! spark_running master org.apache.spark.deploy.master.Master; then
  nohup "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.master.Master --host 127.0.0.1 --port 17077 --webui-port 18080 > "$SPARK_LOG_DIR/master.log" 2>&1 < /dev/null &
  echo $! > "$SPARK_PID_DIR/master.pid"
fi
if ! spark_running worker org.apache.spark.deploy.worker.Worker; then
  nohup "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.worker.Worker --host 127.0.0.1 --webui-port 18081 --cores 2 --memory 2g spark://127.0.0.1:17077 > "$SPARK_LOG_DIR/worker.log" 2>&1 < /dev/null &
  echo $! > "$SPARK_PID_DIR/worker.pid"
fi
for attempt in $(seq 1 30); do
  if hdfs dfsadmin -report 2>/dev/null | grep -q 'Live datanodes (1)'; then
    hdfs dfsadmin -safemode wait
    python - <<'PY'
import json, time, urllib.request
for _ in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:18080/json/', timeout=2) as response:
            info = json.load(response)
        if any(w.get('state') == 'ALIVE' for w in info.get('workers', [])):
            print('Project HDFS and Spark Standalone ready')
            break
    except (OSError, ValueError):
        pass
    time.sleep(1)
else:
    raise SystemExit('Spark worker did not register; inspect project logs')
PY
    exit 0
  fi
  sleep 1
done
echo 'HDFS did not become ready; inspect project runtime logs'; exit 1
