from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from core.utils import ensure_dir

logger = logging.getLogger(__name__)


def generate_quantstats_report(equity: pd.Series, out_html: Path, title: str) -> None:
    import quantstats as qs

    ensure_dir(out_html.parent)
    equity = equity.dropna().astype(float)
    rets = equity.pct_change().dropna()
    if rets.empty:
        # 纸交易首次运行通常只有1个估值点，quantstats无法生成统计；这里生成一个最小可打开的HTML占位。
        html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p>数据点不足（需要至少2个净值点才能生成收益率与统计）。</p>
<p>请在下一次周频运行后再生成完整报告。</p>
</body></html>"""
        out_html.write_text(html, encoding="utf-8")
        logger.warning("净值点数不足，生成占位报告：%s（points=%d）", out_html, len(equity))
        return

    qs.reports.html(rets, output=str(out_html), title=title)
    logger.info("生成报告：%s", out_html)
