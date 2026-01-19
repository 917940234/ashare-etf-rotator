"""
股债轮动策略 - 使用 BT 库实现
"""
import bt
import pandas as pd
import numpy as np
from pathlib import Path
import json

# 加载配置
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def get_asset_map() -> dict:
    """返回 {代码: 名称} 映射"""
    cfg = load_config()
    m = {}
    for a in cfg["assets"]["risk"]:
        m[a["code"]] = a["name"]
    for a in cfg["assets"]["defensive"]:
        m[a["code"]] = a["name"]
    return m


class SetWeights(bt.Algo):
    """
    自定义权重设置算法：从 target.temp["weights"] 读取权重并设置
    这是 BT 库的标准模式
    """
    def __call__(self, target):
        weights = target.temp.get("weights", {})
        if weights:
            target.temp["weights"] = pd.Series(weights)
        return True


class RiskSwitch(bt.Algo):
    """风险开关：检查温度计ETF是否在N月均线之上"""
    def __init__(self, benchmark: str, ma_period: int = 10):
        super().__init__()
        self.benchmark = benchmark
        self.ma_period = ma_period
    
    def __call__(self, target):
        if self.benchmark not in target.universe:
            target.temp["risk_on"] = False
            return True
        
        prices = target.universe[self.benchmark]
        if len(prices) < self.ma_period:
            target.temp["risk_on"] = False
            return True
        
        ma = prices.iloc[-self.ma_period:].mean()
        current = prices.iloc[-1]
        target.temp["risk_on"] = current > ma
        return True


class SelectByMomentum(bt.Algo):
    """动量选股：从风险资产中选择过去N月回报最高的"""
    def __init__(self, risk_assets: list, lookback: int = 6):
        super().__init__()
        self.risk_assets = risk_assets
        self.lookback = lookback
    
    def __call__(self, target):
        if not target.temp.get("risk_on", False):
            target.temp["selected"] = []
            return True
        
        scores = {}
        for sym in self.risk_assets:
            if sym not in target.universe:
                continue
            prices = target.universe[sym]
            if len(prices) < self.lookback + 1:
                continue
            ret = prices.iloc[-1] / prices.iloc[-self.lookback - 1] - 1
            scores[sym] = ret
        
        if not scores:
            target.temp["selected"] = []
            return True
        
        best = max(scores, key=scores.get)
        target.temp["selected"] = [best]
        return True


class WeighRiskDefensive(bt.Algo):
    """根据风险开关设置权重，并写入 target.temp['weights']"""
    def __init__(self, risk_weight: float, defensive_assets: list, defensive_weights: list):
        super().__init__()
        self.risk_weight = risk_weight
        self.defensive_assets = defensive_assets
        self.defensive_weights = defensive_weights
    
    def __call__(self, target):
        weights = {}
        
        if target.temp.get("risk_on", False):
            selected = target.temp.get("selected", [])
            if selected:
                risk_w = self.risk_weight / len(selected)
                for s in selected:
                    weights[s] = risk_w
            
            def_total = 1.0 - self.risk_weight
            for sym, w in zip(self.defensive_assets, self.defensive_weights):
                weights[sym] = def_total * w
        else:
            for sym, w in zip(self.defensive_assets, self.defensive_weights):
                weights[sym] = w
        
        # 转换为 Series 并设置
        target.temp["weights"] = pd.Series(weights)
        return True


def run_backtest(prices: pd.DataFrame, config: dict = None) -> dict:
    """运行 BT 回测"""
    if config is None:
        config = load_config()
    
    cfg = config["strategy"]
    assets = config["assets"]
    
    risk_codes = [a["code"] for a in assets["risk"]]
    def_codes = [a["code"] for a in assets["defensive"]]
    def_weights = [a["weight"] for a in assets["defensive"]]
    benchmark = assets["benchmark"]["code"]
    
    all_codes = list(set(risk_codes + def_codes))
    available = [c for c in all_codes if c in prices.columns]
    prices = prices[available].dropna(how="all")
    
    # 填充缺失值（前向填充，避免 nan）
    prices = prices.ffill().bfill()
    
    if prices.empty:
        return {"error": "无有效数据"}
    
    # 构建策略
    strategy = bt.Strategy(
        "股债轮动",
        [
            bt.algos.RunMonthly(),
            RiskSwitch(benchmark, cfg["risk_switch_ma"]),
            SelectByMomentum(risk_codes, cfg["momentum_months"]),
            WeighRiskDefensive(cfg["risk_weight_on"], def_codes, def_weights),
            bt.algos.Rebalance(),
        ]
    )
    
    # 运行回测
    # 注意：bt 库的 commissions 参数对函数形式有严格要求
    # 使用固定比例费率更稳定，ETF综合费率约 0.031%（不含印花税）
    test = bt.Backtest(strategy, prices, initial_capital=config["paper"]["initial_capital"])
    result = bt.run(test)
    
    # 提取结果
    equity = result[strategy.name].prices
    
    # 计算统计
    total_ret = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
    years = len(equity) / 12
    annual_ret = float(total_ret / years) if years > 0 else 0.0
    
    # 最大回撤
    peak = equity.cummax()
    dd = (peak - equity) / peak
    max_dd = float(dd.max() * 100)
    
    # 月度收益
    monthly_ret = equity.pct_change().dropna()
    sharpe = float(monthly_ret.mean() / monthly_ret.std() * np.sqrt(12)) if monthly_ret.std() > 0 else 0.0
    
    return {
        "total_return": round(total_ret, 2),
        "annual_return": round(annual_ret, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "nav": {str(k)[:10]: round(float(v), 2) for k, v in equity.to_dict().items()},
        "monthly_returns": {str(k)[:10]: round(float(v) * 100, 2) for k, v in monthly_ret.to_dict().items()},
        # 多曲线对比数据
        "benchmarks": get_benchmark_curves(prices, benchmark, equity.index),
    }


def get_benchmark_curves(prices: pd.DataFrame, benchmark_code: str, dates) -> dict:
    """
    获取大盘和基金的基准曲线（归一化为初始值100）
    """
    result = {}
    
    # 获取价格数据中实际存在的日期（取交集）
    available_dates = prices.index.intersection(dates)
    if len(available_dates) == 0:
        return result
    
    # 大盘（沪深300）
    if benchmark_code in prices.columns:
        bench = prices[benchmark_code].reindex(available_dates).dropna()
        if len(bench) > 0:
            normed = (bench / bench.iloc[0] * 100).round(2)
            result["benchmark"] = {
                "name": "沪深300ETF",
                "nav": {str(k)[:10]: float(v) for k, v in normed.to_dict().items()}
            }
    
    # 添加其他主要 ETF 对比
    compare_codes = ["510500", "510880"]  # 中证500、红利
    names = {"510500": "中证500ETF", "510880": "上证红利ETF"}
    
    for code in compare_codes:
        if code in prices.columns and code != benchmark_code:
            ser = prices[code].reindex(available_dates).dropna()
            if len(ser) > 0:
                normed = (ser / ser.iloc[0] * 100).round(2)
                result[code] = {
                    "name": names.get(code, code),
                    "nav": {str(k)[:10]: float(v) for k, v in normed.to_dict().items()}
                }
    
    return result

