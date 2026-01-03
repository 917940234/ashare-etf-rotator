from __future__ import annotations

import json
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


@dataclass
class PaperAccount:
    as_of: str | None
    cash: float
    positions: dict[str, int]
    equity_peak: float
    gate: dict[str, Any]
    history: list[dict[str, Any]]  # {"date": "YYYY-MM-DD", "equity": float}

    @staticmethod
    def new(initial_capital: float, gate_state: dict[str, Any]) -> "PaperAccount":
        return PaperAccount(
            as_of=None,
            cash=float(initial_capital),
            positions={},
            equity_peak=float(initial_capital),
            gate=gate_state,
            history=[],
        )

    @staticmethod
    def load(path: Path) -> "PaperAccount":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return PaperAccount(**raw)

    def save(self, path: Path) -> None:
        ensure_dir(path.parent)
        path.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_prices(market_dir: Path, symbols: list[str]) -> pd.DataFrame:
    frames = []
    for s in symbols:
        p = market_dir / f"{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"缺少本地数据：{p}（请先运行 update-data）")
        df = pd.read_parquet(p)
        frames.append(df[["close"]].rename(columns={"close": s}))
    prices = pd.concat(frames, axis=1).sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.ffill().dropna()
    return prices


def _account_value(account: PaperAccount, price_row: pd.Series) -> float:
    v = float(account.cash)
    for sym, sh in account.positions.items():
        px = float(price_row.get(sym, np.nan))
        if np.isfinite(px):
            v += float(sh) * px
    return float(v)


def run_paper_once(
    market_dir: Path,
    equity_etfs: list[str],
    defensive_etf: str,
    account_path: Path,
    blotter_dir: Path,
    initial_capital: float,
    no_trade_band: float,
    momentum_lookback_days: int,
    vol_lookback_weeks: int,
    vol_floor: float,
    risk_gate_cfg: dict[str, Any],
    allocation_cfg: dict[str, Any],
    cost_model: CostModel,
) -> tuple[pd.DataFrame, pd.Series]:
    symbols = list(dict.fromkeys([*equity_etfs, defensive_etf]))
    prices = _load_prices(market_dir, symbols)
    idx = prices.index
    rebalance_flag = first_day_after_week_end(idx)
    rebalance_dates = idx[rebalance_flag.values]
    if len(rebalance_dates) == 0:
        raise RuntimeError("数据不足以形成周频再平衡日期（需要至少跨过一个周五）")

    if account_path.exists():
        account = PaperAccount.load(account_path)
        logger.info("加载纸交易账户：%s", account_path)
    else:
        gate_state = {"state": RiskState.NORMAL.value, "cooldown_left": 0}
        account = PaperAccount.new(initial_capital=initial_capital, gate_state=gate_state)
        logger.info("初始化纸交易账户：初始资金 %.2f", initial_capital)

    # 选择下一次执行的再平衡日
    if account.as_of:
        last = pd.to_datetime(account.as_of)
        cand = rebalance_dates[rebalance_dates > last]
    else:
        cand = rebalance_dates
    if len(cand) == 0:
        raise RuntimeError("没有可执行的下一次再平衡日（账户已是最新）")
    trade_dt = pd.Timestamp(cand[0])
    signal_dt = idx[idx.get_loc(trade_dt) - 1]

    pre_positions = {k: int(v) for k, v in account.positions.items()}
    pre_cash = float(account.cash)

    # 先把“上次调仓后到本次信号日”的净值按日补齐（仅使用收盘价估值）
    if account.as_of:
        last_as_of = pd.to_datetime(account.as_of)
        fill_dates = idx[(idx > last_as_of) & (idx <= signal_dt)]
        existing_dates = {h.get("date") for h in account.history}
        for d in fill_dates:
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
            if ds in existing_dates:
                continue
            v = _account_value(account, prices.loc[d])
            account.history.append({"date": ds, "equity": float(v)})
            account.equity_peak = max(float(account.equity_peak), float(v))

    gate = RiskGate(**risk_gate_cfg)
    gate.state = RiskState(account.gate.get("state", RiskState.NORMAL.value))
    gate.cooldown_left = int(account.gate.get("cooldown_left", 0))

    # 用 signal_dt 的净值来计算回撤（策略层面）
    signal_value = _account_value(account, prices.loc[signal_dt])
    account.equity_peak = max(float(account.equity_peak), float(signal_value))
    drawdown = 1.0 - signal_value / account.equity_peak if account.equity_peak > 0 else 0.0

    state, changed = gate.on_rebalance(drawdown)
    if changed:
        logger.info("纸交易风控状态切换：%s（signal=%s，drawdown=%.2f%%，cooldown_left=%d）",
                    state.value, signal_dt.date(), drawdown * 100.0, gate.cooldown_left)

    scores = compute_score(
        prices=prices,
        symbols=equity_etfs,
        signal_date=signal_dt,
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

    px_trade = prices.loc[trade_dt]
    pre_value = float(pre_cash)
    for sym, sh in pre_positions.items():
        px = float(px_trade.get(sym, np.nan))
        if np.isfinite(px):
            pre_value += float(sh) * px
    current_weights = {s: 0.0 for s in symbols}
    for s in symbols:
        sh = int(pre_positions.get(s, 0))
        if sh <= 0:
            continue
        current_weights[s] = (sh * float(px_trade[s])) / pre_value if pre_value > 0 else 0.0

    # 应用 no-trade band
    for s, w in list(tw.items()):
        cw = float(current_weights.get(s, 0.0))
        if abs(w - cw) < no_trade_band:
            tw[s] = cw

    # 目标份额（按收盘价成交，ETF按1份为最小单位）
    target_shares: dict[str, int] = {}
    for s, w in tw.items():
        target_value = pre_value * float(w)
        px = float(px_trade[s])
        target_shares[s] = int(np.floor(target_value / px)) if px > 0 else 0

    # 对于当前持仓但不在目标里：目标为0
    for s in list(pre_positions.keys()):
        if s not in target_shares:
            target_shares[s] = 0

    # 生成交易（先卖后买）
    trades = []
    cash = float(pre_cash)
    cost_by_symbol: dict[str, float] = {}

    def est_cost_for(sym: str, dv: float, sv: float) -> float:
        return cost_model.estimate_for_rebalance([{"symbol": sym, "trade_value": dv, "sell_value": sv}])

    # SELL
    for s, tgt in target_shares.items():
        cur = int(account.positions.get(s, pre_positions.get(s, 0)))
        delta = tgt - cur
        if delta >= 0:
            continue
        px = float(px_trade.get(s, np.nan))
        if not np.isfinite(px) or px <= 0:
            continue
        sell_shares = -delta
        sell_value = sell_shares * px
        cost = est_cost_for(s, dv=sell_value, sv=sell_value)
        cash += sell_value - cost
        account.positions[s] = cur - sell_shares
        cost_by_symbol[s] = cost_by_symbol.get(s, 0.0) + float(cost)
        trades.append((s, "SELL", cur, tgt, delta, px, cost))

    # BUY（若现金不足，会按优先级缩减：先权益后防守）
    buy_syms = list(target_shares.keys())
    if defensive_etf in buy_syms:
        buy_syms.remove(defensive_etf)
        buy_syms.append(defensive_etf)

    for s in buy_syms:
        tgt = int(target_shares[s])
        cur = int(account.positions.get(s, pre_positions.get(s, 0)))
        delta = tgt - cur
        if delta <= 0:
            continue
        px = float(px_trade.get(s, np.nan))
        if not np.isfinite(px) or px <= 0:
            continue

        # 尝试买入，若现金不足则减少份额
        buy = delta
        while buy > 0:
            buy_value = buy * px
            cost = est_cost_for(s, dv=buy_value, sv=0.0)
            need = buy_value + cost
            if cash >= need - 1e-6:
                cash -= need
                account.positions[s] = cur + buy
                cost_by_symbol[s] = cost_by_symbol.get(s, 0.0) + float(cost)
                trades.append((s, "BUY", cur, tgt, buy, px, cost))
                break
            buy -= 1

        if buy == 0:
            # 买不进（现金不足）
            tgt2 = int(account.positions.get(s, cur))
            trades.append((s, "HOLD", cur, tgt2, 0, px, 0.0))

    # 清理0持仓
    account.positions = {k: int(v) for k, v in account.positions.items() if int(v) != 0}
    account.cash = float(cash)

    post_value = _account_value(account, px_trade)
    account.as_of = trade_dt.strftime("%Y-%m-%d")
    account.gate = {"state": gate.state.value, "cooldown_left": int(gate.cooldown_left)}
    account.history.append({"date": account.as_of, "equity": float(post_value)})
    account.equity_peak = max(float(account.equity_peak), float(post_value))
    account.save(account_path)

    # 输出交易清单（包含 HOLD 行，方便人工对照）
    rows = []
    union_syms = sorted(set([*symbols, *pre_positions.keys(), *target_shares.keys()]))
    for s in union_syms:
        cur_sh = int(pre_positions.get(s, 0))
        # 目标份额以“执行后持仓”为准（若现金不足会被缩减）
        tgt_sh = int(account.positions.get(s, target_shares.get(s, cur_sh)))
        px = float(px_trade.get(s, np.nan))
        cur_w = float(current_weights.get(s, 0.0))
        tgt_w = float(tw.get(s, 0.0))
        delta = tgt_sh - cur_sh
        action = "HOLD" if delta == 0 else ("BUY" if delta > 0 else "SELL")
        rows.append(
            {
                "trade_date": trade_dt.strftime("%Y-%m-%d"),
                "signal_date": signal_dt.strftime("%Y-%m-%d"),
                "symbol": s,
                "action": action,
                "current_weight": cur_w,
                "target_weight": tgt_w,
                "target_shares": tgt_sh,
                "delta_shares": delta,
                "reference_price": px,
                "estimated_cost": float(cost_by_symbol.get(s, 0.0)),
                "state": gate.state.value,
            }
        )
    blotter = pd.DataFrame(rows)

    ensure_dir(blotter_dir)
    out_csv = blotter_dir / f"paper_trades_{trade_dt.strftime('%Y%m%d')}.csv"
    blotter.to_csv(out_csv, index=False, encoding="utf-8-sig")
    logger.info("纸交易完成：trade_date=%s value=%.2f cash=%.2f positions=%s -> %s",
                trade_dt.date(), post_value, account.cash, account.positions, out_csv)

    # 生成净值序列（用账户历史点，供报告）
    hist = pd.DataFrame(account.history)
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date").drop_duplicates(subset=["date"], keep="last").set_index("date")
    equity_curve = hist["equity"].astype(float)
    return blotter, equity_curve
