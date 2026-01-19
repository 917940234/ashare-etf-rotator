"""
基金行情图表路由 - /api/chart/*
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from data import get_etf_daily, get_all_symbols, get_asset_info

router = APIRouter(prefix="/api/chart", tags=["图表"])


@router.get("/{code}")
def get_chart_data(
    code: str,
    period: str = Query("1y", description="时间周期: 1d, 1w, 1m, 1y, 3y, 5y, all"),
    chart_type: str = Query("line", description="图表类型: line, kline")
):
    """
    获取基金行情数据
    - period: 1d(1天), 1w(1周), 1m(1月), 1y(1年), 3y(3年), 5y(5年), all(全部)
    - chart_type: line(曲线图), kline(K线图)
    """
    # 验证代码
    all_symbols = get_all_symbols()
    if code not in all_symbols:
        raise HTTPException(404, f"基金代码 {code} 不在资产池中")
    
    # 获取数据
    df = get_etf_daily(code)
    if df.empty:
        raise HTTPException(404, f"暂无 {code} 的行情数据")
    
    # 确保日期列格式正确
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    
    # 根据周期筛选数据
    end_date = df["date"].max()
    if period == "1d":
        start_date = end_date - timedelta(days=1)
    elif period == "1w":
        start_date = end_date - timedelta(weeks=1)
    elif period == "1m":
        start_date = end_date - timedelta(days=30)
    elif period == "1y":
        start_date = end_date - timedelta(days=365)
    elif period == "3y":
        start_date = end_date - timedelta(days=365 * 3)
    elif period == "5y":
        start_date = end_date - timedelta(days=365 * 5)
    else:  # all
        start_date = df["date"].min()
    
    df_filtered = df[df["date"] >= start_date].copy()
    
    if df_filtered.empty:
        raise HTTPException(404, "该时间段内无数据")
    
    # 获取资产信息
    asset_info = get_asset_info()
    name = asset_info.get(code, {}).get("name", code)
    
    # 格式化输出
    result = {
        "code": code,
        "name": name,
        "period": period,
        "chart_type": chart_type,
        "data_points": len(df_filtered)
    }
    
    if chart_type == "kline":
        # K线图数据格式: [[date, open, close, low, high], ...]
        result["data"] = [
            [
                row["date"].strftime("%Y-%m-%d"),
                round(float(row["open"]), 3),
                round(float(row["close"]), 3),
                round(float(row["low"]), 3),
                round(float(row["high"]), 3)
            ]
            for _, row in df_filtered.iterrows()
        ]
    else:
        # 曲线图数据格式
        result["dates"] = [d.strftime("%Y-%m-%d") for d in df_filtered["date"]]
        result["prices"] = [round(float(p), 3) for p in df_filtered["close"]]
    
    return result


@router.get("")
def list_available_funds():
    """获取可用的基金列表"""
    asset_info = get_asset_info()
    funds = []
    for code, info in asset_info.items():
        funds.append({
            "code": code,
            "name": info.get("name", code),
            "type": info.get("type", "unknown")
        })
    return {"funds": funds}
