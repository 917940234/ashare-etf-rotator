"""
交易相关路由 - /api/trading/*
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from deps import require_user
from trading import (
    get_or_create_account, buy, sell, reset_account as reset_trading_account,
    calculate_portfolio_value, get_current_prices, get_transactions, get_nav_history
)
from routers.signal import api_get_signal


router = APIRouter(prefix="/api/trading", tags=["交易"])


class BuyRequest(BaseModel):
    symbol: str
    amount: float


class SellRequest(BaseModel):
    symbol: str
    shares: int


class TradeAction(BaseModel):
    action: str
    symbol: Optional[str] = None
    code: Optional[str] = None
    amount: Optional[float] = 0
    shares: Optional[int] = 0
    
    @property
    def effective_symbol(self) -> str:
        return self.symbol or self.code or ""


class BatchTradeRequest(BaseModel):
    actions: list[TradeAction]


@router.get("/account")
def api_get_trading_account(user: dict = Depends(require_user)):
    """获取交易账户信息"""
    account = get_or_create_account(user["id"])
    prices = get_current_prices()
    return calculate_portfolio_value(account, prices)


@router.get("/prices")
def api_get_prices():
    """获取当前价格"""
    return get_current_prices()


@router.post("/buy")
def api_buy(req: BuyRequest, user: dict = Depends(require_user)):
    """买入"""
    success, msg = buy(user["id"], req.symbol, req.amount)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}


@router.post("/sell")
def api_sell(req: SellRequest, user: dict = Depends(require_user)):
    """卖出"""
    success, msg = sell(user["id"], req.symbol, req.shares)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}


@router.get("/transactions")
def api_get_transactions(user: dict = Depends(require_user)):
    """获取交易记录"""
    return get_transactions(user["id"])


@router.get("/history")
def api_get_nav_history(user: dict = Depends(require_user)):
    """获取用户净值历史"""
    return get_nav_history(user["id"])


@router.post("/reset")
def api_reset_my_account(user: dict = Depends(require_user)):
    """重置账户（仅管理员）"""
    if not user["is_admin"]:
        raise HTTPException(403, "普通用户无法重置账户")
    reset_trading_account(user["id"])
    return {"message": "账户已重置"}


@router.get("/advice")
def api_get_trading_advice(user: dict = Depends(require_user), force_refresh: bool = False):
    """获取针对当前用户账户的具体交易建议（支持用户干预检测）"""
    from datetime import datetime, timedelta
    
    signal = api_get_signal()
    if "error" in signal:
        return {"error": signal["error"]}
    
    account = get_or_create_account(user["id"])
    prices = get_current_prices()
    portfolio = calculate_portfolio_value(account, prices)
    
    total_value = portfolio["total_value"]
    current_positions = {p["symbol"]: p for p in portfolio.get("positions", [])}
    
    # ========== 用户干预检测 ==========
    transactions = account.get("transactions", [])
    user_intervention_detected = False
    last_trade_time = None
    recent_manual_trades = []
    
    # 检查最近24小时内的交易（可能是手动操作）
    now = datetime.now()
    for tx in reversed(transactions[-10:]):  # 检查最近10笔交易
        tx_time_str = tx.get("time", "")
        if tx_time_str:
            try:
                tx_time = datetime.fromisoformat(tx_time_str)
                if now - tx_time < timedelta(hours=24):
                    last_trade_time = tx_time_str
                    recent_manual_trades.append(tx)
            except:
                pass
    
    # 如果最近有交易，标记为用户干预
    if recent_manual_trades and not force_refresh:
        user_intervention_detected = True
    
    # ========== 计算目标持仓 ==========
    target_positions = {}
    for rec in signal["recommendation"]:
        code = rec["code"]
        target_weight = rec["weight"] / 100
        target_value = total_value * target_weight
        
        if code in prices:
            price = prices[code]["price"]
            target_shares = int(target_value / price / 100) * 100
            target_positions[code] = {
                "code": code,
                "name": rec["name"],
                "target_weight": rec["weight"],
                "target_value": round(target_value, 2),
                "target_shares": target_shares,
                "price": price,
            }
    
    # ========== 计算偏离度 ==========
    total_deviation = 0
    for code, target in target_positions.items():
        current = current_positions.get(code)
        current_value = current["value"] if current else 0
        deviation = abs(current_value - target["target_value"])
        total_deviation += deviation
    
    # 多余持仓的偏离
    for symbol, pos in current_positions.items():
        if symbol not in target_positions:
            total_deviation += pos["value"]
    
    deviation_pct = (total_deviation / total_value * 100) if total_value > 0 else 0
    
    # 偏离度等级
    if deviation_pct < 5:
        deviation_level = "low"
    elif deviation_pct < 15:
        deviation_level = "medium"
    else:
        deviation_level = "high"
    
    # ========== 智能建议策略 ==========
    suggestion_mode = "auto"  # 默认自动模式
    suggestion_message = None
    
    if user_intervention_detected and not force_refresh:
        if deviation_level == "low":
            suggestion_mode = "manual_detected_ok"
            suggestion_message = "检测到您近期有手动交易，当前持仓与策略偏离较小，无需调整。"
        elif deviation_level == "medium":
            suggestion_mode = "manual_detected_wait"
            suggestion_message = "检测到您近期有手动交易，当前持仓与策略有一定偏离。建议等待下一调仓周期或点击「刷新建议」重新计算。"
        else:
            suggestion_mode = "manual_detected_review"
            suggestion_message = "检测到您近期有手动交易，当前持仓与策略偏离较大。如需调整，请点击「刷新建议」查看最新建议。"
    
    # ========== 生成具体建议 ==========
    actions = []
    
    # 如果是手动检测模式且偏离不大，不生成具体买卖建议
    if suggestion_mode in ("manual_detected_ok", "manual_detected_wait") and not force_refresh:
        actions.append({
            "action": "hold",
            "action_text": "维持现状",
            "code": "-",
            "name": suggestion_message,
            "shares": 0,
            "reason": f"偏离度 {deviation_pct:.1f}%（{deviation_level}）"
        })
    else:
        # 1. 卖出不在目标中的持仓
        for symbol, pos in current_positions.items():
            if symbol not in target_positions:
                actions.append({
                    "action": "sell",
                    "action_text": "卖出",
                    "code": symbol,
                    "name": pos["name"],
                    "shares": pos["shares"],
                    "estimated_value": round(pos["value"], 2),
                    "reason": "不在目标持仓中"
                })
        
        # 2. 调整现有持仓或新建持仓
        for code, target in target_positions.items():
            current = current_positions.get(code)
            
            if current:
                diff_shares = target["target_shares"] - current["shares"]
                if diff_shares > 0:
                    actions.append({
                        "action": "buy",
                        "action_text": "加仓",
                        "code": code,
                        "name": target["name"],
                        "shares": diff_shares,
                        "amount": round(diff_shares * target["price"], 2),
                        "reason": f"目标 {target['target_weight']}%，需加仓"
                    })
                elif diff_shares < 0:
                    actions.append({
                        "action": "sell",
                        "action_text": "减仓",
                        "code": code,
                        "name": target["name"],
                        "shares": abs(diff_shares),
                        "estimated_value": round(abs(diff_shares) * target["price"], 2),
                        "reason": f"目标 {target['target_weight']}%，需减仓"
                    })
            else:
                if target["target_shares"] > 0:
                    actions.append({
                        "action": "buy",
                        "action_text": "买入",
                        "code": code,
                        "name": target["name"],
                        "shares": target["target_shares"],
                        "amount": round(target["target_shares"] * target["price"], 2),
                        "reason": f"目标 {target['target_weight']}%，新建仓"
                    })
        
        # 如果没有任何操作
        if not actions:
            actions.append({
                "action": "hold",
                "action_text": "持有",
                "code": "-",
                "name": "当前持仓符合策略",
                "shares": 0,
                "reason": "无需调整"
            })
    
    return {
        "date": signal["date"],
        "risk_on": signal["risk_on"],
        "total_value": total_value,
        "cash": portfolio["cash"],
        "actions": actions,
        "target_positions": list(target_positions.values()),
        # 新增字段
        "user_intervention_detected": user_intervention_detected,
        "last_trade_time": last_trade_time,
        "deviation_pct": round(deviation_pct, 1),
        "deviation_level": deviation_level,
        "suggestion_mode": suggestion_mode,
        "suggestion_message": suggestion_message,
    }


@router.post("/batch")
def api_batch_trade(req: BatchTradeRequest, user: dict = Depends(require_user)):
    """批量执行交易"""
    results = []
    
    sells = [a for a in req.actions if a.action == 'sell']
    buys = [a for a in req.actions if a.action == 'buy']
    
    for action in sells:
        symbol = action.effective_symbol
        try:
            success, msg = sell(user["id"], symbol, action.shares)
            results.append({"symbol": symbol, "action": "sell", "success": success, "message": msg})
        except Exception as e:
            results.append({"symbol": symbol, "action": "sell", "success": False, "message": str(e)})
            
    for action in buys:
        symbol = action.effective_symbol
        try:
            success, msg = buy(user["id"], symbol, action.amount)
            results.append({"symbol": symbol, "action": "buy", "success": success, "message": msg})
        except Exception as e:
            results.append({"symbol": symbol, "action": "buy", "success": False, "message": str(e)})

    return {"results": results}
