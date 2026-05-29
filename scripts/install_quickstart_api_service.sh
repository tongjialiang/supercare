#!/usr/bin/env bash
# 将 SuperCare API 安装为当前用户的 systemd 常驻服务（关终端不断、开机自启）
set -euo pipefail

PROJECT_ROOT="/srv/supercare"
SERVICE_NAME="supercare-quickstart-api"
PYTHON_BIN="$(command -v python3)"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${USER_UNIT_DIR}/${SERVICE_NAME}.service"
LOG_DIR="${PROJECT_ROOT}/logs"

mkdir -p "${USER_UNIT_DIR}" "${LOG_DIR}"

if [[ ! -f "${PROJECT_ROOT}/supercare_quickstart_api.py" ]]; then
  echo "错误：未找到 ${PROJECT_ROOT}/supercare_quickstart_api.py"
  exit 1
fi

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=SuperCare 快速运行 API (uvicorn :8765)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${PYTHON_BIN} -m uvicorn supercare_quickstart_api:app --host 0.0.0.0 --port 8765
Restart=always
RestartSec=5
TimeoutStopSec=300
StandardOutput=append:${LOG_DIR}/quickstart_api.log
StandardError=append:${LOG_DIR}/quickstart_api.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}"
systemctl --user restart "${SERVICE_NAME}"

# 允许用户未登录时服务仍运行（关机重启后自动拉起）
if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "${USER}" 2>/dev/null || true
fi

echo ""
echo "已安装并启动：${SERVICE_NAME}"
echo "  状态：systemctl --user status ${SERVICE_NAME}"
echo "  日志：tail -f ${LOG_DIR}/quickstart_api.log"
echo "  停止：systemctl --user stop ${SERVICE_NAME}"
echo "  文档：http://127.0.0.1:8765/docs"
