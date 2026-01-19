#!/bin/bash
set -e

# ================= 配置区 =================
ENV_NAME="ashare-etf-rotator"
PYTHON_VER="3.10"
MINICONDA_DIR="$HOME/miniconda3"
CONDA_INIT="$MINICONDA_DIR/etc/profile.d/conda.sh"
# =========================================

echo "🚀 开始初始化项目环境: $ENV_NAME"

# 1. 检查 Conda 是否安装
if [ ! -f "$CONDA_INIT" ]; then
    if [ -d "$MINICONDA_DIR" ]; then
        echo "🧹 清理损坏的 Miniconda 目录..."
        rm -rf "$MINICONDA_DIR"
    fi
    echo "⬇️ 正在下载 Miniconda..."
    wget --no-check-certificate https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p "$MINICONDA_DIR"
    rm miniconda.sh
fi

source "$CONDA_INIT"

# 2. 创建环境
set +e
conda info --envs | grep -q "$ENV_NAME"
ENV_EXISTS=$?
set -e

if [ $ENV_EXISTS -eq 0 ]; then
    echo "✅ 环境 $ENV_NAME 已存在"
else
    echo "📦 正在创建环境 (仅 Python $PYTHON_VER)..."
    conda create -n "$ENV_NAME" python=$PYTHON_VER --override-channels -c conda-forge -y
fi

conda activate "$ENV_NAME"

# 3. PIP 安装 Python 依赖
echo "📥 正在通过 PIP 安装依赖..."
if [ -f "requirements.txt" ]; then
    python -m pip install --upgrade pip
    # 已配置清华源，并显示安装过程
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
else
    echo "⚠️ 未找到 requirements.txt"
fi

# 4. Node.js 环境
if ! command -v npm &> /dev/null; then
    echo "🔧 安装 Node.js..."
    conda install nodejs --override-channels -c conda-forge -y
fi

# 5. 前端依赖安装 (核心修改部分)
if [ -d "frontend" ]; then
    echo "🎨 检查前端依赖..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "⚡️ 正在使用淘宝镜像源加速安装，并开启详细日志..."
        # 修改点：
        # 1. --registry: 指定淘宝源
        # 2. --verbose: 显示所有安装细节，不再只闪烁光标
        npm install --registry=https://registry.npmmirror.com --verbose
    else
        echo "✅ node_modules 已存在，跳过安装"
    fi
    cd ..
fi

# 6. 启动
echo "✅ 准备就绪，启动服务..."
echo "---------------------------------------"
bash scripts/start.sh