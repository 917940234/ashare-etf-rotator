#!/bin/bash
# 启动后端服务

cd "$(dirname "$0")/.."

echo "Starting ETF Rotator Backend..."
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"

uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
