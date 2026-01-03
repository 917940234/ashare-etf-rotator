from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.utils import ensure_dir

logger = logging.getLogger(__name__)


def generate_quantstats_report(equity: pd.Series, out_html: Path, title: str) -> None:
    import quantstats as qs

    ensure_dir(out_html.parent)
    equity = equity.dropna().astype(float)
    rets = equity.pct_change().dropna()
    if rets.empty:
        raise ValueError("收益率序列为空，无法生成报告")
    qs.reports.html(rets, output=str(out_html), title=title)
    logger.info("生成报告：%s", out_html)

