"""
模拟交易账户模块 - 每用户独立账户
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
ACCOUNTS_DIR = DATA_DIR / "accounts"
ACCOUNTS_DIR.mkdir(exist_ok=True)

INITIAL_CAPITAL = 100000.0

# ==================== ETF 交易费用 (2024-2025) ====================
# ETF 交易无印花税
TRADE_FEES = {
    "commission": 0.00025,    # 佣金 0.025%，网上交易优惠费率
    "commission_min": 5.0,    # 佣金最低5元
    "handling_fee": 0.0000341,  # 经手费 0.00341%
    "regulation_fee": 0.00002,  # 证管费 0.002%
    "transfer_fee": 0.00001,   # 过户费 0.001%
}


def calculate_fees(amount: float, is_sell: bool = False) -> dict:
    """
    计算交易费用
    ETF 交易无印花税，买卖双向收取其他费用
    
    Args:
        amount: 交易金额
        is_sell: 是否为卖出（ETF买卖费用相同）
    
    Returns:
        dict: 各项费用明细和总费用
    """
    # 佣金（有最低限制）
    commission = max(amount * TRADE_FEES["commission"], TRADE_FEES["commission_min"])
    # 经手费
    handling_fee = amount * TRADE_FEES["handling_fee"]
    # 证管费
    regulation_fee = amount * TRADE_FEES["regulation_fee"]
    # 过户费
    transfer_fee = amount * TRADE_FEES["transfer_fee"]
    
    total = commission + handling_fee + regulation_fee + transfer_fee
    
    return {
        "commission": round(commission, 2),
        "handling_fee": round(handling_fee, 2),
        "regulation_fee": round(regulation_fee, 2),
        "transfer_fee": round(transfer_fee, 2),
        "total": round(total, 2),
        "rate": round(total / amount * 100, 4) if amount > 0 else 0,  # 实际费率%
    }


def get_account_path(user_id: int) -> Path:
    return ACCOUNTS_DIR / f"user_{user_id}.json"


def get_or_create_account(user_id: int) -> dict:
    """获取或创建用户账户"""
    path = get_account_path(user_id)
    
    if path.exists():
        account = json.loads(path.read_text())
        # 确保旧账户有 nav_history 字段
        if "nav_history" not in account:
            account["nav_history"] = []
            save_account(account)
        return account
    
    # 创建新账户
    account = {
        "user_id": user_id,
        "cash": INITIAL_CAPITAL,
        "initial_capital": INITIAL_CAPITAL,
        "positions": {},  # {symbol: {"shares": int, "avg_cost": float}}
        "transactions": [],  # 交易记录
        "nav_history": [],  # 净值历史 [{"date": str, "value": float}]
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(account, ensure_ascii=False, indent=2))
    return account


def save_account(account: dict):
    """保存账户"""
    account["last_updated"] = datetime.now().isoformat()
    path = get_account_path(account["user_id"])
    path.write_text(json.dumps(account, ensure_ascii=False, indent=2))


def get_current_prices() -> dict:
    """获取当前价格（从最新数据）"""
    from data import load_prices_daily, get_asset_info
    
    prices = load_prices_daily()
    if prices.empty:
        return {}
    
    latest = prices.iloc[-1]
    asset_info = get_asset_info()
    
    result = {}
    for code in latest.index:
        price = latest[code]
        if pd.notna(price):
            info = asset_info.get(code, {})
            result[code] = {
                "price": float(price),
                "name": info.get("name", code),
            }
    return result


def calculate_portfolio_value(account: dict, prices: dict) -> dict:
    """计算投资组合价值"""
    cash = account["cash"]
    positions_value = 0.0
    positions_detail = []
    
    for symbol, pos in account["positions"].items():
        if symbol in prices:
            current_price = prices[symbol]["price"]
            value = pos["shares"] * current_price
            cost = pos["shares"] * pos["avg_cost"]
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            
            positions_detail.append({
                "symbol": symbol,
                "name": prices[symbol].get("name", symbol),
                "shares": pos["shares"],
                "avg_cost": round(pos["avg_cost"], 3),
                "current_price": round(current_price, 3),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
            positions_value += value
    
    total_value = cash + positions_value
    total_pnl = total_value - account["initial_capital"]
    total_pnl_pct = (total_pnl / account["initial_capital"] * 100)
    
    return {
        "cash": round(cash, 2),
        "positions_value": round(positions_value, 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "positions": positions_detail,
        "initial_capital": account["initial_capital"],
    }


def buy(user_id: int, symbol: str, amount: float) -> tuple[bool, str]:
    """
    买入（含交易费用）
    amount: 买入金额
    """
    account = get_or_create_account(user_id)
    prices = get_current_prices()
    
    if symbol not in prices:
        return False, f"未找到标的 {symbol}"
    
    price = prices[symbol]["price"]
    shares = int(amount / price / 100) * 100  # 按100股整数买入
    
    if shares == 0:
        return False, "金额不足买入100股"
    
    cost = shares * price
    # 计算交易费用
    fees = calculate_fees(cost, is_sell=False)
    total_cost = cost + fees["total"]
    
    if total_cost > account["cash"]:
        return False, f"现金不足，需要 {total_cost:.2f}（含费用 {fees['total']:.2f}），可用 {account['cash']:.2f}"
    
    # 更新持仓（成本包含费用）
    if symbol in account["positions"]:
        old_pos = account["positions"][symbol]
        old_cost = old_pos["shares"] * old_pos["avg_cost"]
        new_shares = old_pos["shares"] + shares
        new_avg_cost = (old_cost + total_cost) / new_shares
        account["positions"][symbol] = {"shares": new_shares, "avg_cost": new_avg_cost}
    else:
        account["positions"][symbol] = {"shares": shares, "avg_cost": total_cost / shares}
    
    # 更新现金
    account["cash"] -= total_cost
    
    # 记录交易（含费用明细）
    account["transactions"].append({
        "type": "buy",
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "amount": cost,
        "fees": fees,
        "total_cost": total_cost,
        "time": datetime.now().isoformat(),
    })
    
    # 记录净值历史
    _record_nav_history(account, prices)
    
    save_account(account)
    return True, f"买入 {symbol} {shares}股，成交价 {price:.3f}，金额 {cost:.2f}，费用 {fees['total']:.2f}（{fees['rate']:.3f}%）"


def sell(user_id: int, symbol: str, shares: int) -> tuple[bool, str]:
    """卖出（含交易费用）"""
    account = get_or_create_account(user_id)
    prices = get_current_prices()
    
    if symbol not in prices:
        return False, f"未找到标的 {symbol}"
    
    if symbol not in account["positions"]:
        return False, f"未持有 {symbol}"
    
    pos = account["positions"][symbol]
    if shares > pos["shares"]:
        return False, f"持有 {pos['shares']}股，无法卖出 {shares}股"
    
    price = prices[symbol]["price"]
    amount = shares * price
    # 计算交易费用
    fees = calculate_fees(amount, is_sell=True)
    net_amount = amount - fees["total"]
    
    # 更新持仓
    if shares == pos["shares"]:
        del account["positions"][symbol]
    else:
        account["positions"][symbol]["shares"] -= shares
    
    # 更新现金（扣除费用后的净额）
    account["cash"] += net_amount
    
    # 记录交易（含费用明细）
    account["transactions"].append({
        "type": "sell",
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "amount": amount,
        "fees": fees,
        "net_amount": net_amount,
        "time": datetime.now().isoformat(),
    })
    
    # 记录净值历史
    _record_nav_history(account, prices)
    
    save_account(account)
    return True, f"卖出 {symbol} {shares}股，成交价 {price:.3f}，金额 {amount:.2f}，费用 {fees['total']:.2f}，实得 {net_amount:.2f}"


def reset_account(user_id: int) -> dict:
    """重置账户"""
    path = get_account_path(user_id)
    if path.exists():
        path.unlink()
    return get_or_create_account(user_id)


def get_transactions(user_id: int, limit: int = 20) -> list:
    """获取交易记录"""
    account = get_or_create_account(user_id)
    return account["transactions"][-limit:][::-1]


def _record_nav_history(account: dict, prices: dict):
    """记录净值历史（每日只记录一次）"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 计算当前净值
    portfolio = calculate_portfolio_value(account, prices)
    total_value = portfolio["total_value"]
    
    # 检查今天是否已记录
    if account["nav_history"]:
        last_record = account["nav_history"][-1]
        if last_record["date"] == today:
            # 更新今天的记录
            account["nav_history"][-1]["value"] = total_value
            return
    
    # 添加新记录
    account["nav_history"].append({
        "date": today,
        "value": total_value
    })
    
    # 只保留最近 365 天
    account["nav_history"] = account["nav_history"][-365:]


def get_nav_history(user_id: int) -> list:
    """获取用户净值历史"""
    account = get_or_create_account(user_id)
    return account.get("nav_history", [])
