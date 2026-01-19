"""
回测相关路由 - /api/backtest
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from data import load_prices_monthly, load_config
from strategy import run_backtest


router = APIRouter(prefix="/api", tags=["回测"])


class BacktestRequest(BaseModel):
    start_date: str = "2015-01-01"
    end_date: Optional[str] = None
    risk_weight: float = 0.35
    ma_period: int = 10
    momentum_months: int = 6


@router.post("/backtest")
def api_backtest(req: BacktestRequest):
    """运行回测"""
    cfg = load_config()
    cfg["strategy"]["risk_weight_on"] = req.risk_weight
    cfg["strategy"]["risk_switch_ma"] = req.ma_period
    cfg["strategy"]["momentum_months"] = req.momentum_months
    
    prices = load_prices_monthly()
    if prices.empty:
        raise HTTPException(400, "无数据，请先更新")
    
    start = datetime.strptime(req.start_date, "%Y-%m-%d")
    end = datetime.strptime(req.end_date, "%Y-%m-%d") if req.end_date else datetime.now()
    prices = prices[(prices.index >= start) & (prices.index <= end)]
    
    if len(prices) < 12:
        raise HTTPException(400, "数据不足12个月，请先更新数据")
    
    result = run_backtest(prices, cfg)
    if "error" in result:
        raise HTTPException(500, result["error"])
    
    return result
