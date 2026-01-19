"""
数据服务模块 - 使用 AKShare 获取 ETF 日线数据，Parquet 本地缓存
支持返回月频数据供 BT 库使用
"""
import pandas as pd
import akshare as ak
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def get_all_symbols() -> list:
    """获取配置中所有 ETF 代码"""
    cfg = load_config()
    codes = []
    for a in cfg["assets"]["risk"]:
        codes.append(a["code"])
    for a in cfg["assets"]["defensive"]:
        codes.append(a["code"])
    return list(set(codes))


def get_asset_info() -> dict:
    """返回资产信息 {code: {name, desc/weight, type}}"""
    cfg = load_config()
    info = {}
    for a in cfg["assets"]["risk"]:
        info[a["code"]] = {"name": a["name"], "desc": a.get("desc", ""), "type": "risk"}
    for a in cfg["assets"]["defensive"]:
        info[a["code"]] = {"name": a["name"], "weight": a["weight"], "type": "defensive"}
    return info


def get_etf_daily(symbol: str, start: str = "20100101", end: str = None) -> pd.DataFrame:
    """
    获取单个 ETF 的日线数据，优先从本地缓存读取，增量更新
    """
    if end is None:
        end = datetime.now().strftime("%Y%m%d")
    
    cache_path = DATA_DIR / f"{symbol}.parquet"
    
    # 尝试读取缓存
    cached_df = pd.DataFrame()
    if cache_path.exists():
        try:
            cached_df = pd.read_parquet(cache_path)
            cached_df["date"] = pd.to_datetime(cached_df["date"])
        except Exception as e:
            logger.warning(f"缓存损坏，将重新下载: {e}")
            cache_path.unlink()
    
    # 计算需要下载的日期范围
    if not cached_df.empty:
        last_date = cached_df["date"].max()
        fetch_start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
        if fetch_start > end:
            logger.info(f"{symbol} 数据已是最新")
            return cached_df
    else:
        fetch_start = start
    
    # 从 AKShare 下载
    logger.info(f"下载 {symbol}: {fetch_start} -> {end}")
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol, 
            period="daily", 
            start_date=fetch_start, 
            end_date=end
        )
    except Exception as e:
        logger.error(f"下载 {symbol} 失败: {e}")
        return cached_df
    
    if df.empty:
        return cached_df
    
    # 标准化列名
    df = df.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume"
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "open", "high", "low", "close", "volume"]]
    
    # 合并缓存
    if not cached_df.empty:
        df = pd.concat([cached_df, df]).drop_duplicates("date").sort_values("date")
    
    # 保存
    df.reset_index(drop=True).to_parquet(cache_path)
    logger.info(f"{symbol} 已保存 {len(df)} 条记录")
    
    return df


def update_universe() -> dict:
    """更新所有配置中的 ETF 数据"""
    symbols = get_all_symbols()
    results = {}
    asset_info = get_asset_info()
    
    for sym in symbols:
        try:
            df = get_etf_daily(sym)
            name = asset_info.get(sym, {}).get("name", sym)
            results[sym] = {
                "status": "ok", 
                "rows": len(df),
                "name": name,
                "last_date": str(df["date"].max())[:10] if len(df) > 0 else None
            }
        except Exception as e:
            results[sym] = {"status": "error", "message": str(e)}
    
    # 记录更新时间
    _save_update_time()
    
    return results


def _get_update_time_path() -> Path:
    """获取更新时间记录文件路径"""
    return DATA_DIR / "last_update.json"


def _save_update_time():
    """保存数据更新时间"""
    import json
    path = _get_update_time_path()
    data = {
        "last_update": datetime.now().isoformat(),
        "updated_by": "system"
    }
    path.write_text(json.dumps(data, ensure_ascii=False))


def get_last_update_time() -> dict:
    """获取最后更新时间"""
    import json
    path = _get_update_time_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return {"last_update": None, "updated_by": None}



def load_prices_daily(symbols: list = None) -> pd.DataFrame:
    """加载日频收盘价宽表"""
    if symbols is None:
        symbols = get_all_symbols()
    
    frames = []
    for sym in symbols:
        path = DATA_DIR / f"{sym}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)[["date", "close"]].rename(columns={"close": sym})
        df["date"] = pd.to_datetime(df["date"])
        frames.append(df.set_index("date"))
    
    if not frames:
        return pd.DataFrame()
    
    return pd.concat(frames, axis=1).sort_index()


def load_prices_monthly(symbols: list = None) -> pd.DataFrame:
    """加载月频收盘价宽表（月末）- 供 BT 库使用"""
    daily = load_prices_daily(symbols)
    if daily.empty:
        return daily
    
    # 转换为月频（月末）
    monthly = daily.resample("ME").last()
    return monthly.dropna(how="all")


def get_data_status() -> dict:
    """获取数据状态"""
    symbols = get_all_symbols()
    asset_info = get_asset_info()
    status = {}
    
    for sym in symbols:
        path = DATA_DIR / f"{sym}.parquet"
        info = asset_info.get(sym, {})
        name = info.get("name", sym)
        
        if path.exists():
            df = pd.read_parquet(path)
            status[sym] = {
                "name": name,
                "type": info.get("type", "unknown"),
                "rows": len(df),
                "last_date": str(df["date"].max())[:10] if len(df) > 0 else None
            }
        else:
            status[sym] = {
                "name": name,
                "type": info.get("type", "unknown"),
                "rows": 0, 
                "last_date": None
            }
    
    return status
