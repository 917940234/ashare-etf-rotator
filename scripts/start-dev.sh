#!/bin/bash
# 开发模式启动脚本 - 支持热更新

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ashare-etf-rotator

cd "$(dirname "$0")/.."

echo "=========================================="
echo "      股债轮动系统 v0.1 [开发模式]"
echo "=========================================="

# 清理旧进程
echo "清理旧进程..."
pkill -f "uvicorn main:app" 2>/dev/null || true
lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
sleep 1

echo "Starting Backend..."
cd src
PYTHONUNBUFFERED=1 python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

sleep 3

echo "Starting Frontend (dev mode)..."
cd frontend
NEXT_TELEMETRY_DISABLED=1 stdbuf -oL -eL npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8000/docs"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop..."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

wait
