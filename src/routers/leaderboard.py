"""
排行榜功能路由 - /api/leaderboard
"""
from fastapi import APIRouter
import sqlite3
from pathlib import Path

from auth import DB_PATH, _generate_default_avatar
from trading import get_or_create_account, get_current_prices, calculate_portfolio_value


router = APIRouter(prefix="/api/leaderboard", tags=["排行榜"])


@router.get("")
def api_get_leaderboard():
    """获取韭菜排行榜（收益率倒序 = 亏损最多在前）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, avatar FROM users")
    users = c.fetchall()
    conn.close()
    
    prices = get_current_prices()
    rankings = []
    
    for user_id, username, avatar in users:
        try:
            account = get_or_create_account(user_id)
            portfolio = calculate_portfolio_value(account, prices)
            
            rankings.append({
                "user_id": user_id,
                "username": username,
                "avatar": avatar or _generate_default_avatar(username),
                "total_value": portfolio["total_value"],
                "total_pnl": portfolio["total_pnl"],
                "total_pnl_pct": portfolio["total_pnl_pct"],
            })
        except Exception:
            # 用户可能没有交易账户
            rankings.append({
                "user_id": user_id,
                "username": username,
                "avatar": avatar or _generate_default_avatar(username),
                "total_value": 100000,
                "total_pnl": 0,
                "total_pnl_pct": 0,
            })
    
    # 按收益率倒序排序（亏损最多在前 = 韭菜排行榜）
    rankings.sort(key=lambda x: x["total_pnl_pct"])
    
    # 添加排名
    for i, r in enumerate(rankings):
        r["rank"] = i + 1
    
    return rankings
