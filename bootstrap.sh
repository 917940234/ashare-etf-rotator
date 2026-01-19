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

# 4. Node.js 环境 (使用 NVM 管理，用户级别安装，无需 sudo)
NODE_VER="22"  # LTS 版本
NVM_DIR="$HOME/.nvm"

# 安装或加载 NVM
if [ ! -d "$NVM_DIR" ]; then
    echo "⬇️ 正在安装 NVM..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi

# 加载 NVM（无论是新安装还是已存在）
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# 检查 Node.js 版本，不满足则安装
NEED_INSTALL=false
if ! command -v node &> /dev/null; then
    echo "⚠️ 未检测到 Node.js"
    NEED_INSTALL=true
else
    CURRENT_NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$CURRENT_NODE_VER" -lt "$NODE_VER" ]; then
        echo "⚠️ 当前 Node.js 版本过低 (v$CURRENT_NODE_VER)，需要 v$NODE_VER+"
        NEED_INSTALL=true
    else
        echo "✅ Node.js $(node -v) 满足要求"
    fi
fi

if [ "$NEED_INSTALL" = true ]; then
    echo "📦 正在通过 NVM 安装 Node.js v$NODE_VER..."
    nvm install "$NODE_VER"
    nvm use "$NODE_VER"
    nvm alias default "$NODE_VER"
    echo "✅ Node.js $(node -v) / npm $(npm -v) 安装完成"
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