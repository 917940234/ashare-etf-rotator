"""
策略信号相关路由 - /api/signal
"""
from fastapi import APIRouter

from data import load_prices_monthly, load_config, get_asset_info


router = APIRouter(prefix="/api", tags=["策略信号"])


@router.get("/signal")
def api_get_signal():
    """获取当前月度信号"""
    cfg = load_config()
    asset_info = get_asset_info()
    prices = load_prices_monthly()
    
    if prices.empty or len(prices) < cfg["strategy"]["risk_switch_ma"] + 1:
        return {"error": "数据不足"}
    
    benchmark = cfg["assets"]["benchmark"]["code"]
    ma_period = cfg["strategy"]["risk_switch_ma"]
    
    if benchmark in prices.columns:
        bench_prices = prices[benchmark].dropna()
        ma = float(bench_prices.iloc[-ma_period:].mean())
        current = float(bench_prices.iloc[-1])
        risk_on = bool(current > ma)
        raw_ratio = round(current / ma, 4) if ma > 0 else 0.0
    else:
        risk_on = False
        ma = 0.0
        current = 0.0
        raw_ratio = 0.0
    
    # 计算动量
    risk_assets = []
    for asset in cfg["assets"]["risk"]:
        code = asset["code"]
        momentum = 0.0
        if code in prices.columns:
            series = prices[code].dropna()
            if len(series) >= cfg["strategy"]["momentum_months"] + 1:
                months = cfg["strategy"]["momentum_months"]
                start_p = float(series.iloc[-(months + 1)])
                end_p = float(series.iloc[-1])
                momentum = round((end_p / start_p - 1) * 100, 2)
        risk_assets.append({
            "code": code,
            "name": asset.get("name", code),
            "momentum": momentum
        })
    
    # 排序风险资产
    risk_assets.sort(key=lambda x: x["momentum"], reverse=True)
    
    # 推荐持仓
    recommendation = []
    if risk_on:
        top_risk = risk_assets[0]
        risk_w = cfg["strategy"]["risk_weight_on"]
        
        recommendation.append({
            "code": top_risk["code"],
            "name": top_risk["name"] + " (优选)",
            "weight": round((1.0 - risk_w) * 100, 1),
            "type": "risk"
        })
        
        for da in cfg["assets"]["defensive"]:
           recommendation.append({
               "code": da["code"],
               "name": da.get("name", da["code"]),
               "weight": round(da["weight"] * risk_w * 100, 1),
               "type": "defensive"
           })
    else:
        for da in cfg["assets"]["defensive"]:
           recommendation.append({
               "code": da["code"],
               "name": da.get("name", da["code"]),
               "weight": round(da["weight"] * 100, 1),
               "type": "defensive"
           })
    
    # 生成策略解释
    bench_name = next((a["name"] for a in cfg["assets"]["risk"] + [cfg["assets"]["benchmark"]] if a["code"] == benchmark), benchmark)
    top_name = risk_assets[0]["name"] if risk_assets else "未知"
    
    if risk_on:
        strategy_text = (
            f"当前 {bench_name} 价格 ({round(current, 3)}) 位于 {ma_period} 月均线 ({round(ma, 3)}) 上方，"
            f"市场趋势向好 (比率 {raw_ratio})。策略判定为【进攻模式】。\n"
            f"在权益类资产中，{top_name} 动量最强 ({risk_assets[0]['momentum']}%)，建议重点持有。"
        )
    else:
        strategy_text = (
            f"当前 {bench_name} 价格 ({round(current, 3)}) 跌破 {ma_period} 月均线 ({round(ma, 3)})，"
            f"市场趋势转弱 (比率 {raw_ratio})。策略触发【防御机制】。\n"
            f"建议清仓权益类资产，全仓转入债券/货币类 ETF 避险，等待趋势反转。"
        )

    return {
        "date": str(prices.index[-1].date()),
        "risk_on": risk_on,
        "benchmark": {
            "name": bench_name,
            "current": current,
            "ma": ma,
            "raw_ratio": raw_ratio
        },
        "risk_assets": risk_assets,
        "recommendation": recommendation,
        "strategy_text": strategy_text
    }
