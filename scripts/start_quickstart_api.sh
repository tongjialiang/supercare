#!/usr/bin/env bash
# 后台启动 API（关终端仍运行；机器重启后需重新执行或改用 systemd）
set -euo pipefail

PROJECT_ROOT="/srv/supercare"
PID_FILE="${PROJECT_ROOT}/.quickstart_api.pid"
LOG_FILE="${PROJECT_ROOT}/logs/quickstart_api.log"
PORT=8765

mkdir -p "${PROJECT_ROOT}/logs"
cd "${PROJECT_ROOT}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "API 已在运行，PID=$(cat "${PID_FILE}")"
  exit 0
fi

nohup python3 -m uvicorn supercare_quickstart_api:app \
  --host 0.0.0.0 --port "${PORT}" >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
echo "已后台启动，PID=$(cat "${PID_FILE}")"
echo "日志：${LOG_FILE}"
echo "文档：http://127.0.0.1:${PORT}/docs"
