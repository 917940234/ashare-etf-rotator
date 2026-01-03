# A股ETF周频轮动（AKShare + bt）——回测 + 纸交易 + 报告

> 仅供研究与学习，不构成任何投资建议。市场有风险，投资需谨慎。

这是一个“小型、个人、低频（周频）”的A股场内ETF量化研究项目，面向量化新手：  
用 **AKShare** 拉取ETF日线并本地 **Parquet** 缓存；用 **bt** 做周频再平衡回测；用 **quantstats** 生成HTML报告；并提供“半自动实盘前”的 **纸交易**（生成交易清单，用户手动在券商APP下单）。

## 关键约束（已满足）
- 数据源：仅 AKShare（公开行情），回测完全依赖本地 `data/` 缓存，不在回测时在线请求。
- 回测引擎：仅 `bt`（pmorissette/bt）。
- 本地缓存：Parquet（`pyarrow`）。
- 报告：`quantstats` 输出HTML到 `reports/`。
- 实盘：不接券商API，仅生成交易清单（半自动）。

## 策略概要（默认，可在配置修改）
- 备选权益ETF：`510300, 510500, 159915, 588000`
- 防守ETF：`511360`
- 每周一次：**周五收盘后**计算信号，**下一交易日**执行再平衡  
  - 本项目在回测与纸交易中统一使用“**下一交易日收盘价成交**”的假设（避免未来函数、实现简单且一致）。
- 信号：
  - 动量：过去 `60` 个交易日收益率（≈12周）
  - 波动惩罚：过去 `12` 周周收益率标准差
  - `score = momentum / volatility`（对缺失/0波动做稳健处理）
  - 每周从权益池中选 `score` 最高的1只作为权益持仓
- 同时持仓不超过2只：权益1只 + 防守1只
- 风控闸门（策略净值层面，显式状态机写日志与交易清单）：
  - 回撤 ≥ 15%：`DE-RISK`（权益上限50%，其余防守）
  - 回撤 ≥ 30%：`CIRCUIT-COOLDOWN`（防守100%，冷静期4周；冷静期内不持有权益）
  - 冷静期结束后恢复信号机制（若仍触发阈值会再次进入对应状态）
- 再平衡缓冲带：目标权重与当前权重偏离 < 2% 则不交易

## 成本模型（参数化近似，重要）
`bt` 的内置费用模型不方便表达“**单笔最低佣金5元**”，本项目采用“再平衡日组合价值扣减成本”的近似：

对每个发生交易的标的 i：
```
trade_value_i = |Δw_i| * portfolio_value
sell_value_i  = max(w_before_i - w_after_i, 0) * portfolio_value

cost_i = max(trade_value_i * commission_rate, min_commission)
         + sell_value_i * stamp_tax_rate
         + trade_value_i * (slippage_bps / 10000)
```
组合在再平衡日执行后通过 `bt.Strategy.adjust(-total_cost)` 扣减现金。

局限性（已在代码与输出中保持保守）：
- 按“权重变化”估算成交额，未做逐笔拆分，且不做份额整数/最小申赎单位约束；
- 佣金最低5元按“每个发生交易的标的”计入，未细分买卖方向拆单；
- 使用“下一交易日收盘价成交”是假设，实际成交价格与滑点会不同；
- 实际券商费率/最低收费以券商为准。

## 目录结构
```
app/        核心代码（数据、策略、回测、纸交易、报告、CLI）
config/     配置文件
data/       本地Parquet缓存（运行后生成）
reports/    HTML报告（运行后生成）
logs/       日志（运行后生成）
scripts/    脚本（冒烟测试）
```

## 安装
建议创建虚拟环境（可选）：
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```
在 Debian/Ubuntu 上如果 `python3 -m venv` 报错，通常需要安装系统包 `python3-venv`（不同Python版本包名可能略有区别）。

## 快速开始（推荐顺序）
1) 更新数据（首次全量，后续增量）
```bash
python -m app.cli update-data
```

2) 运行回测并生成报告
```bash
python -m app.cli run-backtest
```
输出位置：
- 回测日志：`logs/app.log`
- 回测报告：`reports/backtest_report.html`
- 回测再平衡记录：`reports/backtest_rebalances.csv`

3) 运行一次纸交易（只执行“下一次”周频调仓）
```bash
python -m app.cli run-paper
```
输出位置：
- 纸交易日志：`logs/app.log`
- 纸交易交易清单：`reports/paper_trades_YYYYMMDD.csv`
- 纸交易报告：`reports/paper_report.html`
- 纸交易账户状态：`data/paper/account.json`

4) 冒烟测试（会：更新数据→跑一次回测→生成报告）
```bash
python scripts/smoke_test.py
```

## 实际应用（周频、半自动下单）推荐流程
1) 周五（或本周最后一个交易日）收盘后：
```bash
python -m app.cli update-data
python -m app.cli plan-weekly
```
查看输出的 `reports/weekly_plan_YYYYMMDD.csv`，按其中 `target_weight` 与 `state` 决定下周一在券商APP手动下单的标的与大致仓位（参考价为周五收盘价）。

2) 下一个交易日收盘后（用于复盘/对账与纸交易记账）：
```bash
python -m app.cli update-data
python -m app.cli run-paper
```
`run-paper` 会用“下一交易日收盘价成交”的统一假设更新 `data/paper/account.json`，并输出当周交易清单 `reports/paper_trades_YYYYMMDD.csv`。

5) 仅从已缓存净值曲线重生成报告
```bash
python -m app.cli generate-report --source backtest
python -m app.cli generate-report --source paper
```

## 配置（`config/config.yaml`）
你可以修改：
- ETF池（权益/防守）
- 动量/波动窗口
- 风控阈值与冷静期周数
- 执行价格假设（本项目统一为“下一交易日收盘价”）
- 成本参数：佣金率、最低佣金、印花税（卖出）、滑点bps
- 初始资金（默认2万元）

## 免责声明
- 本项目仅供研究学习，不构成投资建议。
- 免费数据源可能不稳定，因此必须本地缓存；回测使用缓存数据以保证可复现。
- 成本模型为近似，实际费用以券商为准；本项目通过参数化与保守估计降低偏差风险。
