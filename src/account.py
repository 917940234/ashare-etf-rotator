"""
纸交易账户管理 - 使用 JSON 文件持久化
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
ACCOUNT_FILE = DATA_DIR / "paper_account.json"


def _load_account() -> dict:
    """加载账户"""
    if ACCOUNT_FILE.exists():
        return json.loads(ACCOUNT_FILE.read_text())
    return None


def _save_account(account: dict):
    """保存账户"""
    DATA_DIR.mkdir(exist_ok=True)
    ACCOUNT_FILE.write_text(json.dumps(account, indent=2, ensure_ascii=False))


def init_account(initial_capital: float = 100000.0) -> dict:
    """初始化账户"""
    account = {
        "cash": initial_capital,
        "positions": {},  # {symbol: shares}
        "history": [],    # 净值历史
        "trades": [],     # 交易记录
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_account(account)
    return account


def get_account() -> Optional[dict]:
    """获取账户"""
    return _load_account()


def get_or_create_account(initial_capital: float = 100000.0) -> dict:
    """获取或创建账户"""
    account = _load_account()
    if account is None:
        account = init_account(initial_capital)
    return account


def update_account(
    cash: Optional[float] = None,
    positions: Optional[dict] = None,
    trade: Optional[dict] = None,
    nav_point: Optional[tuple] = None,  # (date_str, value)
) -> dict:
    """更新账户"""
    account = get_or_create_account()
    
    if cash is not None:
        account["cash"] = cash
    
    if positions is not None:
        account["positions"] = positions
    
    if trade is not None:
        account["trades"].append({
            **trade,
            "timestamp": datetime.now().isoformat()
        })
        # 只保留最近100条
        account["trades"] = account["trades"][-100:]
    
    if nav_point is not None:
        account["history"].append({"date": nav_point[0], "value": nav_point[1]})
        # 只保留最近52周
        account["history"] = account["history"][-52:]
    
    account["updated_at"] = datetime.now().isoformat()
    _save_account(account)
    return account


def reset_account(initial_capital: float = 100000.0) -> dict:
    """重置账户"""
    return init_account(initial_capital)
