from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def today_yyyymmdd() -> str:
    return dt.date.today().strftime("%Y%m%d")


def to_date_index(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col]).dt.tz_localize(None)
    out = out.sort_values(col)
    out = out.drop_duplicates(subset=[col], keep="last")
    out = out.set_index(col)
    out.index.name = "date"
    return out


def first_day_after_week_end(dates: pd.DatetimeIndex) -> pd.Series:
    """
    返回布尔序列：是否为“W-FRI 周期”的第一天（即周五收盘后的下一交易日）。
    """
    if len(dates) == 0:
        return pd.Series([], dtype=bool)
    periods = dates.to_period("W-FRI")
    prev = periods.shift(1)
    flag = pd.Series(periods != prev, index=dates)
    flag.iloc[0] = False
    return flag
