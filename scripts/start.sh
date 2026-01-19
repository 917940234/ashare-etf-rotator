#!/bin/bash

# 加载并激活 Conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ashare-etf-rotator

cd "$(dirname "$0")/.."

# 可选：自定义 JWT 密钥（生产环境建议设置）
# export JWT_SECRET_KEY="your-custom-secret-key"

echo "=========================================="
echo "      股债轮动系统 v0.1"
echo "=========================================="

# 清理旧进程
echo "清理旧进程..."
pkill -f "uvicorn main:app" 2>/dev/null || true
lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
sleep 1

echo "Starting Backend..."
cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

sleep 3

echo "Starting Frontend..."
cd frontend
# 禁用版本检查避免网络超时
NEXT_TELEMETRY_DISABLED=1 npm run dev &
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