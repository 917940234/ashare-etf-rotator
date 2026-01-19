# A股 ETF 轮动系统 v0.1

> **声明**：仅供学习研究，不构成投资建议。

## 极简设计理念

*   **无框架回测**：纯 Pandas 实现，~200 行代码
*   **无数据库**：JSON 文件存储配置和账户
*   **最少依赖**：后端仅 5 个核心库

## 快速启动

```bash
# 1. 安装后端依赖
pip3 install -r requirements.txt

# 2. 安装前端依赖
cd frontend && npm install && cd ..

# 3. 启动
bash scripts/start.sh
```

*   前端: http://localhost:3000
*   后端 API: http://localhost:8000/docs

## 核心功能

1.  **更新数据**: 从 AKShare 拉取 ETF 日线
2.  **本周信号**: 按动量/波动率评分，推荐持仓
3.  **回测**: 查看策略历史表现

## 项目结构

```
├── src/              # Python 后端
│   ├── main.py       # FastAPI 入口
│   ├── data.py       # AKShare 数据服务
│   ├── backtest.py   # 回测引擎
│   └── account.py    # 纸交易账户
├── frontend/         # Next.js 前端
├── config.json       # 配置文件
└── data/             # 数据存储
```

## 配置说明 (`config.json`)

```json
{
  "universe": {
    "equity": ["510300", "510500"],  // 参与轮动的ETF
    "bond": ["511010"]                // 避险资产
  },
  "strategy": {
    "momentum_days": 20,  // 动量窗口
    "hold_count": 1       // 持有数量
  }
}
```
