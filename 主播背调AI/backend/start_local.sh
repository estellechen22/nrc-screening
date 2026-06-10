#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="/opt/anaconda3/bin/python3"
PORT="${PORT:-8000}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] Python not found at $PYTHON_BIN"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR"
cd "$PROJECT_DIR"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "[WARN] 未设置 ADMIN_TOKEN，配置接口将不可用。"
  echo "[WARN] 请先在 .env 中设置 ADMIN_TOKEN 后重启。"
fi

echo "[INFO] 启动主播风险筛查系统..."
echo "[INFO] URL: http://127.0.0.1:${PORT}"
exec "$PYTHON_BIN" -m uvicorn app:app --host 0.0.0.0 --port "$PORT" --reload
