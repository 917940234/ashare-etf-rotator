#!/bin/bash
set -e

echo "🚀 开始更新项目..."

# 1. 拉取最新代码
echo "⬇️ 正在拉取 git 代码..."
git pull

# 2. 重新运行 bootstrap.sh
# bootstrap.sh 会处理依赖安装（pip/npm）并自动调用 start.sh 重启服务
echo "🔄 正在调用 bootstrap.sh 进行依赖更新和重启..."
bash bootstrap.sh
