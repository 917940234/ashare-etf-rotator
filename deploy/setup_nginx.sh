#!/bin/bash
set -e

# 确保在项目根目录运行
cd "$(dirname "$0")/.."

echo "🔧 开始配置 Nginx 反向代理..."

# 1. 安装 Nginx
if ! command -v nginx &> /dev/null; then
    echo "📦 安装 Nginx..."
    apt update
    apt install -y nginx
else
    echo "✅ Nginx 已安装"
fi

# 2. 部署配置
echo "📄 部署配置文件..."
if [ ! -f "deploy/nginx-yhdmt.conf" ]; then
    echo "❌ 错误：找不到 deploy/nginx-yhdmt.conf"
    exit 1
fi

cp deploy/nginx-yhdmt.conf /etc/nginx/sites-available/yhdmt.cloud

# 3.不仅用配置
# 删除默认配置（如果存在）
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
    echo "🗑️  已移除默认配置 default"
fi

# 建立软链接
if [ -L /etc/nginx/sites-enabled/yhdmt.cloud ]; then
    unlink /etc/nginx/sites-enabled/yhdmt.cloud
fi
ln -s /etc/nginx/sites-available/yhdmt.cloud /etc/nginx/sites-enabled/

# 4. 检查并重载
echo "🔍 检查 Nginx 配置..."
nginx -t

echo "🔄 重载 Nginx..."
systemctl reload nginx

echo "==============================================="
echo "✅ Nginx 配置完成！"
echo "👉 访问地址: http://www.yhdmt.cloud"
echo "            http://38.95.79.13"
echo "==============================================="
