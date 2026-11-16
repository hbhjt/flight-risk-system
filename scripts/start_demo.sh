#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
FLIGHT_RUNTIME="${FLIGHT_RUNTIME:-/mnt/d/flight-risk-runtime}"
FLIGHT_PYTHON="${FLIGHT_PYTHON:-$FLIGHT_RUNTIME/venv/bin/python}"
for item in artifacts/flight.sqlite artifacts/predictions.sqlite frontend/dist/index.html results/m3/metrics.json; do
  if [[ ! -f "$item" ]]; then
    printf '缺少演示文件：%s。请按 README 生成或解压带数据的演示包。\n' "$item" >&2
    exit 1
  fi
done
if [[ ! -x "$FLIGHT_PYTHON" ]]; then
  printf '未找到独立 Python：%s。请按 README 创建环境。\n' "$FLIGHT_PYTHON" >&2
  exit 1
fi
printf '网页地址：http://localhost:%s/\n按 Ctrl+C 关闭。演示不需要重新训练或启动集群。\n' "${FLIGHT_PORT:-18000}"
exec "$FLIGHT_PYTHON" -m uvicorn backend.app:app --host 127.0.0.1 --port "${FLIGHT_PORT:-18000}"
