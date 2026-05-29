#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/srv/supercare"
PID_FILE="${PROJECT_ROOT}/.quickstart_api.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "未找到 PID 文件，服务可能未通过 start_quickstart_api.sh 启动"
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  echo "已停止 API，PID=${PID}"
else
  echo "进程 ${PID} 不存在"
fi
rm -f "${PID_FILE}"
