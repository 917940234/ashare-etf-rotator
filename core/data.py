from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from core.utils import ensure_dir, today_yyyymmdd, to_date_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketDataStore:
    market_dir: Path

    def path_for(self, symbol: str) -> Path:
        return self.market_dir / f"{symbol}.parquet"

    def has(self, symbol: str) -> bool:
        return self.path_for(symbol).exists()

    def load(self, symbol: str) -> pd.DataFrame:
        p = self.path_for(symbol)
        df = pd.read_parquet(p)
        df = df.reset_index()
        df = to_date_index(df, col="date")
        return df

    def save(self, symbol: str, df: pd.DataFrame) -> None:
        ensure_dir(self.market_dir)
        out = df.copy()
        out.index = pd.to_datetime(out.index).tz_localize(None)
        out.index.name = "date"
        out.to_parquet(self.path_for(symbol), index=True)


def _normalize_akshare_etf_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or getattr(df, "empty", True) or len(getattr(df, "columns", [])) == 0:
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "amount"])
        empty.index = pd.DatetimeIndex([], name="date")
        return empty

    rename = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    out = df.rename(columns=rename).copy()
    if "date" not in out.columns:
        raise ValueError(f"AKShare返回字段缺少日期列，实际列：{list(df.columns)}")
    keep = ["date", "open", "high", "low", "close", "volume", "amount"]
    for c in keep:
        if c not in out.columns:
            out[c] = pd.NA
    out = out[keep]
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["date", "close"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    out = to_date_index(out, col="date")
    return out


def _akshare_fetch_etf_daily(
    symbol: str, start_date: str, end_date: str | None
) -> pd.DataFrame:
    import akshare as ak

    end = end_date or today_yyyymmdd()
    try:
        raw = ak.fund_etf_hist_em(
            symbol=symbol, period="daily", start_date=start_date, end_date=end, adjust=""
        )
    except TypeError:
        # 兼容不同版本的参数签名
        raw = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end)
    return _normalize_akshare_etf_daily(raw)


def update_etf_daily(
    store: MarketDataStore,
    symbol: str,
    start_date: str,
    end_date: str | None,
    attempts: int = 5,
    wait_seconds: int = 2,
) -> pd.DataFrame:
    ensure_dir(store.market_dir)

    @retry(stop=stop_after_attempt(attempts), wait=wait_fixed(wait_seconds))
    def _fetch(s: str, sdate: str, edate: str | None) -> pd.DataFrame:
        return _akshare_fetch_etf_daily(s, sdate, edate)

    if store.has(symbol):
        existing = store.load(symbol)
        last_date = existing.index.max()
        next_date = (last_date + pd.Timedelta(days=1)).strftime("%Y%m%d")
        logger.info("增量更新 %s：已有至 %s，拉取 %s~%s", symbol, last_date.date(), next_date, end_date or "今天")
        new = _fetch(symbol, next_date, end_date)
        if new.empty:
            logger.info("增量更新 %s：无新增数据（可能尚未更新到目标日期）", symbol)
            merged = existing
        else:
            merged = pd.concat([existing, new], axis=0)
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        logger.info("首次全量拉取 %s：%s~%s", symbol, start_date, end_date or "今天")
        merged = _fetch(symbol, start_date, end_date)
        if merged.empty:
            raise RuntimeError(f"首次拉取 {symbol} 返回空数据，请稍后重试或检查AKShare接口状态")

    store.save(symbol, merged)
    logger.info("保存 %s：%d 行 -> %s", symbol, len(merged), store.path_for(symbol))
    return merged


def update_universe(
    store: MarketDataStore,
    symbols: Iterable[str],
    start_date: str,
    end_date: str | None,
    attempts: int,
    wait_seconds: int,
) -> None:
    for s in symbols:
        try:
            update_etf_daily(
                store=store,
                symbol=s,
                start_date=start_date,
                end_date=end_date,
                attempts=attempts,
                wait_seconds=wait_seconds,
            )
        except Exception:
            logger.exception("更新数据失败：%s", s)
            raise
