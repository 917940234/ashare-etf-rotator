"""
回测引擎 - 纯 Pandas 向量化实现，无任何外部框架
"""
import pandas as pd
import numpy as np
from typing import Optional


def compute_momentum(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    计算动量因子: 过去 N 天的收益率
    
    Args:
        prices: 收盘价宽表 (date x symbols)
        window: 回看天数
    
    Returns:
        动量因子矩阵
    """
    return prices.pct_change(window)


def compute_volatility(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    计算波动率: 过去 N 天日收益的标准差
    """
    daily_ret = prices.pct_change()
    return daily_ret.rolling(window).std()


def compute_score(prices: pd.DataFrame, momentum_days: int = 20) -> pd.DataFrame:
    """
    计算综合得分: 动量 / 波动率 (风险调整后的动量)
    """
    mom = compute_momentum(prices, momentum_days)
    vol = compute_volatility(prices, momentum_days)
    vol = vol.replace(0, np.nan).clip(lower=0.001)  # 避免除零
    return mom / vol


def backtest(
    prices: pd.DataFrame,
    equity_symbols: list[str],
    bond_symbol: str,
    momentum_days: int = 20,
    hold_count: int = 1,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.00025,
    slippage_bps: float = 5,
    rebalance_freq: str = "W-FRI",  # 每周五调仓
) -> dict:
    """
    向量化回测主函数
    
    Args:
        prices: 收盘价宽表
        equity_symbols: 参与轮动的权益类 ETF
        bond_symbol: 避险资产
        momentum_days: 动量回看天数
        hold_count: 持有标的数量
        initial_capital: 初始资金
        commission_rate: 佣金费率
        slippage_bps: 滑点(基点)
        rebalance_freq: 调仓频率
    
    Returns:
        回测结果字典
    """
    # 确保有数据
    all_symbols = equity_symbols + [bond_symbol]
    prices = prices[all_symbols].dropna()
    
    if len(prices) < momentum_days + 10:
        return {"error": "数据不足"}
    
    # 计算得分 (只对权益类)
    scores = compute_score(prices[equity_symbols], momentum_days)
    
    # 生成调仓信号 (每周五)
    weekly = prices.resample(rebalance_freq).last()
    weekly_scores = scores.resample(rebalance_freq).last()
    
    # 初始化持仓
    portfolio_value = [initial_capital]
    positions = pd.DataFrame(0.0, index=weekly.index, columns=all_symbols)
    cash = initial_capital
    holdings = {}  # {symbol: shares}
    
    rebalance_records = []
    
    for i, date in enumerate(weekly.index[1:], 1):
        prev_date = weekly.index[i-1]
        
        # 获取当前价格
        curr_prices = weekly.loc[date]
        prev_prices = weekly.loc[prev_date]
        
        # 计算持仓市值
        mkt_value = sum(holdings.get(s, 0) * curr_prices[s] for s in all_symbols)
        total_value = cash + mkt_value
        
        # 选股: 得分最高的 N 只
        if not weekly_scores.loc[prev_date].isna().all():
            ranked = weekly_scores.loc[prev_date].sort_values(ascending=False)
            winners = ranked.head(hold_count).index.tolist()
        else:
            winners = [bond_symbol]  # fallback
        
        # 目标权重
        target_weight = 1.0 / len(winners) if winners else 0
        target_holdings = {s: target_weight for s in winners}
        
        # 调仓
        trades = []
        slippage_cost = 0
        commission_cost = 0
        
        # 先卖
        for sym in list(holdings.keys()):
            if sym not in target_holdings or target_holdings[sym] == 0:
                shares = holdings.pop(sym, 0)
                if shares > 0:
                    price = curr_prices[sym] * (1 - slippage_bps / 10000)
                    proceeds = shares * price
                    comm = max(proceeds * commission_rate, 5)  # 最低5元
                    cash += proceeds - comm
                    commission_cost += comm
                    trades.append({"symbol": sym, "action": "SELL", "shares": shares, "price": price})
        
        # 再买
        for sym in winners:
            target_value = total_value * target_weight
            current_value = holdings.get(sym, 0) * curr_prices[sym]
            diff = target_value - current_value
            
            if diff > 100:  # 只有差额大于100元才交易
                price = curr_prices[sym] * (1 + slippage_bps / 10000)
                shares_to_buy = int(diff / price / 100) * 100  # 整百股
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    comm = max(cost * commission_rate, 5)
                    if cash >= cost + comm:
                        cash -= cost + comm
                        holdings[sym] = holdings.get(sym, 0) + shares_to_buy
                        commission_cost += comm
                        trades.append({"symbol": sym, "action": "BUY", "shares": shares_to_buy, "price": price})
        
        # 记录
        mkt_value = sum(holdings.get(s, 0) * curr_prices[s] for s in all_symbols)
        total_value = cash + mkt_value
        portfolio_value.append(total_value)
        
        if trades:
            rebalance_records.append({
                "date": date.strftime("%Y-%m-%d"),
                "trades": trades,
                "value": total_value,
                "commission": commission_cost
            })
    
    # 构建净值曲线
    nav = pd.Series(portfolio_value, index=weekly.index[:len(portfolio_value)])
    nav = nav / nav.iloc[0]  # 归一化
    
    # 计算统计指标
    returns = nav.pct_change().dropna()
    total_return = (nav.iloc[-1] / nav.iloc[0] - 1) * 100
    annual_return = total_return / (len(nav) / 52) if len(nav) > 52 else total_return
    max_drawdown = ((nav.cummax() - nav) / nav.cummax()).max() * 100
    sharpe = returns.mean() / returns.std() * np.sqrt(52) if returns.std() > 0 else 0
    
    return {
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe": round(sharpe, 2),
        "nav": nav.to_dict(),
        "rebalances": rebalance_records[-20:],  # 最近20条
        "final_holdings": holdings,
        "final_cash": cash,
    }
