#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_NAME="ashare-etf-rotator"

if ! command -v conda >/dev/null 2>&1; then
  echo "未找到 conda，请先安装/初始化 Miniconda" >&2
  exit 1
fi

if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "创建 conda 环境：$ENV_NAME"
  conda create -n "$ENV_NAME" python=3.10 -y
fi

echo "安装/更新 Python 依赖（requirements.txt）"
conda run -n "$ENV_NAME" python -m pip install -U pip
conda run -n "$ENV_NAME" python -m pip install -r requirements.txt

if ! command -v node >/dev/null 2>&1; then
  echo "未找到 Node.js，请先安装 Node.js（建议 18+）" >&2
  exit 1
fi

if command -v ss >/dev/null 2>&1; then
  if ss -ltn | awk '{print $4}' | grep -qE '(:|\\])8000$'; then
    echo "端口 8000 已被占用，请先停止占用该端口的进程。" >&2
    exit 1
  fi
  if ss -ltn | awk '{print $4}' | grep -qE '(:|\\])3000$'; then
    echo "端口 3000 已被占用，请先停止占用该端口的进程。" >&2
    exit 1
  fi
fi

echo "安装/更新前端依赖（pnpm）"
corepack enable >/dev/null 2>&1 || true
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && pnpm install)
fi

echo "启动后端 API：http://127.0.0.1:8000"
conda run -n "$ENV_NAME" uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info &
BACK_PID=$!
sleep 1
if ! kill -0 "$BACK_PID" 2>/dev/null; then
  echo "后端启动失败，请检查依赖与端口占用。" >&2
  exit 1
fi

echo "启动前端 UI：http://127.0.0.1:3000"
(cd frontend && pnpm dev) &
FRONT_PID=$!

cleanup() {
  echo "正在停止..."
  kill "$FRONT_PID" 2>/dev/null || true
  kill "$BACK_PID" 2>/dev/null || true
  wait "$FRONT_PID" 2>/dev/null || true
  wait "$BACK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
