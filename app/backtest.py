from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.costs import CostModel
from app.strategy import RiskGate, RiskState, compute_score, pick_best_equity, target_weights
from app.utils import ensure_dir, first_day_after_week_end

logger = logging.getLogger(__name__)


def _load_close_prices(market_dir: Path, symbols: list[str]) -> pd.DataFrame:
    frames = []
    for s in symbols:
        p = market_dir / f"{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"缺少本地数据：{p}（请先运行 update-data）")
        df = pd.read_parquet(p)
        if "close" not in df.columns:
            raise ValueError(f"数据缺少 close 列：{p}")
        frames.append(df[["close"]].rename(columns={"close": s}))
    prices = pd.concat(frames, axis=1).sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices


@dataclass
class BacktestOutputs:
    equity_curve: pd.Series
    rebalance_records: pd.DataFrame
    stats: dict[str, Any]


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def run_bt_backtest(
    market_dir: Path,
    equity_etfs: list[str],
    defensive_etf: str,
    initial_capital: float,
    no_trade_band: float,
    momentum_lookback_days: int,
    vol_lookback_weeks: int,
    vol_floor: float,
    risk_gate_cfg: dict[str, Any],
    allocation_cfg: dict[str, Any],
    cost_model: CostModel,
) -> BacktestOutputs:
    import bt

    symbols = list(dict.fromkeys([*equity_etfs, defensive_etf]))
    prices = _load_close_prices(market_dir, symbols).dropna(how="all")
    prices = prices.ffill().dropna()
    if len(prices) < 200:
        logger.warning("可用数据较少（%d行），回测结果可能不稳定", len(prices))

    idx = prices.index
    rebalance_flag = first_day_after_week_end(idx)

    class DailyRecorder(bt.Algo):
        def __init__(self) -> None:
            super().__init__()

        def __call__(self, target) -> bool:
            d = target.now
            v = float(target.value)
            perm = target.perm
            perm.setdefault("equity_by_date", {})[d] = v
            perm.setdefault("peak_by_date", {})
            prev_peak = perm.get("peak", v)
            peak = max(prev_peak, v)
            perm["peak"] = peak
            perm["peak_by_date"][d] = peak
            return True

    class RunWeeklyAfterFriday(bt.Algo):
        def __call__(self, target) -> bool:
            now = target.now
            i = idx.get_loc(now)
            if i <= 0:
                return False
            if not bool(rebalance_flag.iloc[i]):
                return False
            signal_date = idx[i - 1]
            target.temp["signal_date"] = signal_date
            return True

    class ComputeTarget(bt.Algo):
        def __init__(self) -> None:
            super().__init__()
            self.gate = RiskGate(**risk_gate_cfg)

        def __call__(self, target) -> bool:
            perm = target.perm
            signal_date: pd.Timestamp = target.temp["signal_date"]

            equity_by_date: dict = perm.get("equity_by_date", {})
            peak_by_date: dict = perm.get("peak_by_date", {})
            signal_value = float(equity_by_date.get(signal_date, target.value))
            peak_value = float(peak_by_date.get(signal_date, perm.get("peak", signal_value)))
            drawdown = 1.0 - (signal_value / peak_value) if peak_value > 0 else 0.0

            state, changed = self.gate.on_rebalance(drawdown)
            if changed:
                logger.info("风控状态切换：%s（signal=%s，drawdown=%.2f%%，cooldown_left=%d）",
                            state.value, signal_date.date(), drawdown * 100.0, self.gate.cooldown_left)

            scores = compute_score(
                prices=prices,
                symbols=equity_etfs,
                signal_date=signal_date,
                momentum_lookback_days=momentum_lookback_days,
                vol_lookback_weeks=vol_lookback_weeks,
                vol_floor=vol_floor,
            )
            winner = pick_best_equity(scores, fallback=equity_etfs[0])

            tw = target_weights(
                state=state,
                equity_symbol=winner,
                defensive_symbol=defensive_etf,
                normal_equity_weight=float(allocation_cfg["normal_equity_weight"]),
                derisk_equity_weight=float(allocation_cfg["derisk_equity_weight"]),
            )

            # 记录再平衡前的权重（用于no-trade band与费用估算）
            pre_weights = {}
            total = float(target.value)
            for s in symbols:
                child = target.children.get(s)
                if child is None:
                    pre_weights[s] = 0.0
                else:
                    pre_weights[s] = float(child.value) / total if total > 0 else 0.0

            # no-trade band：偏离<band则保持现状（允许留现金）
            adj = {}
            for s, w in tw.items():
                cw = float(pre_weights.get(s, 0.0))
                if abs(w - cw) < no_trade_band:
                    adj[s] = cw
                else:
                    adj[s] = w
            tw = adj

            target.temp["weights"] = tw
            target.temp["state"] = state.value
            target.temp["winner"] = winner
            target.temp["drawdown"] = drawdown
            target.temp["signal_value"] = signal_value
            target.temp["peak_value"] = peak_value
            target.temp["pre_weights"] = pre_weights
            target.temp["pre_value"] = float(target.value)
            return True

    class ApplyCosts(bt.Algo):
        def __call__(self, target) -> bool:
            pre_weights: dict[str, float] = target.temp.get("pre_weights", {})
            pre_value = float(target.temp.get("pre_value", target.value))
            total_value = float(target.value)
            if total_value <= 0:
                return True

            post_weights = {}
            for s in symbols:
                child = target.children.get(s)
                post_weights[s] = float(child.value) / total_value if child is not None else 0.0

            trades = []
            turnover = 0.0
            gross_trade_value = 0.0
            gross_sell_value = 0.0
            for s in symbols:
                w0 = float(pre_weights.get(s, 0.0))
                w1 = float(post_weights.get(s, 0.0))
                dw = abs(w1 - w0)
                if dw <= 0:
                    continue
                trade_value = dw * pre_value
                sell_value = max(w0 - w1, 0.0) * pre_value
                trades.append({"symbol": s, "trade_value": trade_value, "sell_value": sell_value})
                turnover += dw
                gross_trade_value += trade_value
                gross_sell_value += sell_value

            total_cost = cost_model.estimate_for_rebalance(trades)
            if total_cost > 0:
                target.adjust(-total_cost)

            perm = target.perm
            # 用“扣费后的日终净值”覆盖记录，保证风控统计口径更一致
            perm.setdefault("equity_by_date", {})[target.now] = float(target.value)
            prev_peak = float(perm.get("peak", target.value))
            peak = max(prev_peak, float(target.value))
            perm["peak"] = peak
            perm.setdefault("peak_by_date", {})[target.now] = peak

            rec = {
                "trade_date": target.now.date().isoformat(),
                "signal_date": target.temp["signal_date"].date().isoformat(),
                "state": target.temp["state"],
                "winner": target.temp["winner"],
                "drawdown": float(target.temp["drawdown"]),
                "portfolio_value_pre": float(pre_value),
                "portfolio_value_post": float(target.value),
                "turnover_abs_weight": float(turnover),
                "turnover_oneway": float(turnover / 2.0),
                "gross_trade_value": float(gross_trade_value),
                "gross_sell_value": float(gross_sell_value),
                "estimated_cost": float(total_cost),
            }
            perm.setdefault("rebalance_records", []).append(rec)
            return True

    strategy = bt.Strategy(
        "etf_rotator",
        algos=[
            DailyRecorder(),
            RunWeeklyAfterFriday(),
            bt.algos.SelectAll(),
            ComputeTarget(),
            bt.algos.WeighTarget(),
            bt.algos.Rebalance(),
            ApplyCosts(),
        ],
    )

    backtest = bt.Backtest(strategy, prices, initial_capital=initial_capital)
    res = bt.run(backtest)
    equity = res.prices[strategy.name].copy()
    equity.index = pd.to_datetime(equity.index).tz_localize(None)

    records = pd.DataFrame(strategy.perm.get("rebalance_records", []))
    rets = equity.pct_change().dropna()
    std = float(rets.std()) if not rets.empty else float("nan")
    sharpe = float(np.sqrt(252.0) * float(rets.mean()) / std) if (np.isfinite(std) and std > 0) else float("nan")

    est_cost = float(records["estimated_cost"].sum()) if not records.empty else 0.0
    avg_turnover = float(records["turnover_oneway"].mean()) if not records.empty else 0.0
    cost_over_gross = (
        float(est_cost / records["gross_trade_value"].sum()) if (not records.empty and records["gross_trade_value"].sum() > 0) else float("nan")
    )
    stats = {
        "cagr": float((equity.iloc[-1] / equity.iloc[0]) ** (252.0 / len(equity)) - 1.0),
        "max_drawdown": _max_drawdown(equity),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
        "sharpe": sharpe,
        "avg_weekly_turnover_oneway": avg_turnover,
        "estimated_total_cost": est_cost,
        "estimated_cost_pct_initial": float(est_cost / initial_capital) if initial_capital > 0 else float("nan"),
        "estimated_cost_over_gross_trade": cost_over_gross,
    }
    return BacktestOutputs(equity_curve=equity, rebalance_records=records, stats=stats)
