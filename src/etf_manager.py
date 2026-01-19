"""
ETF 管理模块 - 联网获取 ETF 信息，动态管理资产池
"""
import json
import akshare as ak
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
DATA_DIR = Path(__file__).parent.parent / "data"
ETF_CACHE_PATH = DATA_DIR / "etf_cache.pkl"
CACHE_EXPIRE_HOURS = 1  # 缓存有效期1小时


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=4))


# ==================== ETF 缓存管理 ====================
_etf_cache = None
_cache_time = None


def get_etf_list(force_refresh: bool = False) -> pd.DataFrame:
    """
    获取 ETF 列表（带缓存）
    - 优先从内存缓存读取
    - 其次从本地文件缓存读取
    - 最后从网络下载并缓存
    """
    global _etf_cache, _cache_time
    
    # 1. 检查内存缓存
    if not force_refresh and _etf_cache is not None and _cache_time is not None:
        if datetime.now() - _cache_time < timedelta(hours=CACHE_EXPIRE_HOURS):
            logger.debug("使用内存缓存的 ETF 列表")
            return _etf_cache
    
    # 2. 检查文件缓存
    if not force_refresh and ETF_CACHE_PATH.exists():
        try:
            file_mtime = datetime.fromtimestamp(ETF_CACHE_PATH.stat().st_mtime)
            if datetime.now() - file_mtime < timedelta(hours=CACHE_EXPIRE_HOURS):
                logger.info("从本地缓存加载 ETF 列表...")
                _etf_cache = pd.read_pickle(ETF_CACHE_PATH)
                _cache_time = file_mtime
                logger.info(f"加载完成，共 {len(_etf_cache)} 只 ETF")
                return _etf_cache
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
    
    # 3. 从网络下载
    logger.info("正在从网络下载 ETF 列表（可能需要几秒钟）...")
    try:
        df = ak.fund_etf_spot_em()
        # 保存到文件缓存
        DATA_DIR.mkdir(exist_ok=True)
        df.to_pickle(ETF_CACHE_PATH)
        # 更新内存缓存
        _etf_cache = df
        _cache_time = datetime.now()
        logger.info(f"下载完成，共 {len(df)} 只 ETF，已缓存")
        return df
    except Exception as e:
        logger.error(f"下载 ETF 列表失败: {type(e).__name__}: {e}")
        # 如果有旧缓存，返回旧缓存
        if _etf_cache is not None:
            logger.warning("使用旧缓存")
            return _etf_cache
        return pd.DataFrame()


def fetch_etf_info(code: str) -> dict:
    """
    获取 ETF 信息（从缓存查询，速度快）
    """
    try:
        df = get_etf_list()
        if df.empty:
            return {"code": code, "name": f"ETF-{code}", "found": False, "error": "无法获取ETF列表"}
        
        row = df[df["代码"] == code]
        if not row.empty:
            name = row.iloc[0]["名称"]
            return {"code": code, "name": name, "found": True}
        else:
            logger.warning(f"未找到 ETF {code}")
    except Exception as e:
        logger.error(f"获取 ETF {code} 信息失败: {type(e).__name__}: {e}")
    
    return {"code": code, "name": f"ETF-{code}", "found": False, "error": "未找到"}


def search_etf(keyword: str, limit: int = 20) -> list:
    """
    搜索 ETF（从缓存查询，速度快）
    """
    if not keyword or len(keyword.strip()) < 1:
        return []
    
    try:
        df = get_etf_list()
        if df.empty:
            return []
        
        # 搜索代码或名称
        keyword = keyword.strip()
        mask = (
            df["代码"].str.contains(keyword, case=False, na=False) | 
            df["名称"].str.contains(keyword, na=False)
        )
        results = df[mask].head(limit)
        
        if results.empty:
            return []
        
        result_list = []
        for _, row in results.iterrows():
            try:
                result_list.append({
                    "code": row["代码"],
                    "name": row["名称"],
                    "price": float(row["最新价"]) if pd.notna(row["最新价"]) else None,
                    "change_pct": float(row["涨跌幅"]) if pd.notna(row["涨跌幅"]) else None,
                })
            except:
                continue
        
        return result_list
        
    except Exception as e:
        logger.error(f"搜索 ETF 失败: {type(e).__name__}: {e}")
        return []


def add_asset(asset_type: str = None, code: str = None, name: str = None, weight: float = None, desc: str = None) -> tuple[bool, str]:
    """
    添加资产到池（自动判断类型）
    如果不指定 asset_type，系统会根据 ETF 名称自动判断
    """
    config = load_config()
    
    # 检查是否已存在
    existing_codes = [a["code"] for a in config["assets"]["risk"]] + \
                     [a["code"] for a in config["assets"]["defensive"]]
    if code in existing_codes:
        return False, f"资产 {code} 已存在"
    
    # 获取 ETF 信息
    info = fetch_etf_info(code)
    if not name:
        name = info["name"]
    
    # 自动判断类型（根据名称关键词）
    bond_keywords = ["债", "货币", "添益", "理财", "利率", "久期"]
    is_bond = any(kw in name for kw in bond_keywords)
    
    if asset_type is None:
        asset_type = "defensive" if is_bond else "risk"
    
    # 构建资产对象
    if asset_type == "risk":
        asset = {"code": code, "name": name, "desc": desc or ""}
        config["assets"]["risk"].append(asset)
        type_name = "股票类"
    elif asset_type == "defensive":
        # 债券类自动计算权重：平均分配
        current_count = len(config["assets"]["defensive"])
        if weight is None:
            # 重新平均分配所有债券的权重
            new_weight = round(1.0 / (current_count + 1), 2)
            for a in config["assets"]["defensive"]:
                a["weight"] = new_weight
            weight = new_weight
        asset = {"code": code, "name": name, "weight": weight}
        config["assets"]["defensive"].append(asset)
        type_name = "债券类"
    else:
        return False, f"未知资产类型: {asset_type}"
    
    save_config(config)
    return True, f"已添加到{type_name}：{name} ({code})"


def remove_asset(code: str) -> tuple[bool, str]:
    """
    从池中移除资产
    """
    config = load_config()
    
    # 不能移除 benchmark
    if config["assets"]["benchmark"]["code"] == code:
        return False, "不能移除温度计资产"
    
    # 从 risk 中移除
    original_len = len(config["assets"]["risk"])
    config["assets"]["risk"] = [a for a in config["assets"]["risk"] if a["code"] != code]
    if len(config["assets"]["risk"]) < original_len:
        save_config(config)
        return True, f"已从股票池移除 {code}"
    
    # 从 defensive 中移除
    original_len = len(config["assets"]["defensive"])
    config["assets"]["defensive"] = [a for a in config["assets"]["defensive"] if a["code"] != code]
    if len(config["assets"]["defensive"]) < original_len:
        save_config(config)
        return True, f"已从债券池移除 {code}"
    
    return False, f"未找到资产 {code}"


def update_all_names() -> dict:
    """
    批量更新所有 ETF 名称（强制刷新缓存获取最新数据）
    """
    # 强制刷新缓存获取最新数据
    get_etf_list(force_refresh=True)
    
    config = load_config()
    updated = []
    
    all_assets = config["assets"]["risk"] + config["assets"]["defensive"]
    
    for asset in all_assets:
        info = fetch_etf_info(asset["code"])
        if info["found"] and info["name"] != asset["name"]:
            old_name = asset["name"]
            asset["name"] = info["name"]
            updated.append({"code": asset["code"], "old": old_name, "new": info["name"]})
    
    # 更新 benchmark
    bench = config["assets"]["benchmark"]
    info = fetch_etf_info(bench["code"])
    if info["found"] and info["name"] != bench["name"]:
        updated.append({"code": bench["code"], "old": bench["name"], "new": info["name"]})
        bench["name"] = info["name"]
    
    save_config(config)
    return {"updated": updated, "count": len(updated)}


def get_all_assets() -> dict:
    """
    获取所有资产（带完整信息）
    """
    config = load_config()
    return {
        "risk": config["assets"]["risk"],
        "defensive": config["assets"]["defensive"],
        "benchmark": config["assets"]["benchmark"],
    }
