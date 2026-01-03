from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RiskState(str, Enum):
    NORMAL = "NORMAL"
    DE_RISK = "DE-RISK"
    CIRCUIT_COOLDOWN = "CIRCUIT-COOLDOWN"


@dataclass
class RiskGate:
    derisk_drawdown: float
    circuit_drawdown: float
    cooldown_weeks: int

    state: RiskState = RiskState.NORMAL
    cooldown_left: int = 0

    def next_state(self, drawdown: float) -> RiskState:
        if self.state == RiskState.CIRCUIT_COOLDOWN:
            if self.cooldown_left > 0:
                return RiskState.CIRCUIT_COOLDOWN
            # 冷静期结束后按当前回撤重新评估
        if drawdown >= self.circuit_drawdown:
            return RiskState.CIRCUIT_COOLDOWN
        if drawdown >= self.derisk_drawdown:
            return RiskState.DE_RISK
        return RiskState.NORMAL

    def on_rebalance(self, drawdown: float) -> tuple[RiskState, bool]:
        """
        在每次再平衡“信号时点”调用，返回 (new_state, changed)。
        冷静期以“周频再平衡次数”为单位递减。
        """
        prev = self.state
        new = self.next_state(drawdown)

        # 冷静期语义：进入熔断当周起算，合计 cooldown_weeks 次周频再平衡都保持防守。
        if new == RiskState.CIRCUIT_COOLDOWN and prev != RiskState.CIRCUIT_COOLDOWN:
            self.cooldown_left = max(int(self.cooldown_weeks) - 1, 0)
            self.state = RiskState.CIRCUIT_COOLDOWN
            return self.state, True

        if prev == RiskState.CIRCUIT_COOLDOWN:
            if self.cooldown_left > 0:
                self.cooldown_left -= 1
                self.state = RiskState.CIRCUIT_COOLDOWN
                return self.state, False

        self.state = new
        return self.state, (new != prev)


def compute_score(
    prices: pd.DataFrame,
    symbols: Iterable[str],
    signal_date: pd.Timestamp,
    momentum_lookback_days: int,
    vol_lookback_weeks: int,
    vol_floor: float,
) -> pd.Series:
    """
    score = momentum / volatility
    - momentum: 过去 N 个交易日收益率（close）
    - volatility: 过去 M 周的周收益波动（W-FRI）
    """
    px = prices.loc[:signal_date, list(symbols)].dropna(how="all")
    scores: dict[str, float] = {}
    for s in symbols:
        ser = px[s].dropna()
        if len(ser) < momentum_lookback_days + 1:
            scores[s] = float("-inf")
            continue
        mom = ser.iloc[-1] / ser.iloc[-(momentum_lookback_days + 1)] - 1.0

        weekly = ser.resample("W-FRI").last().pct_change().dropna()
        if len(weekly) < vol_lookback_weeks:
            scores[s] = float("-inf")
            continue
        vol = float(weekly.tail(vol_lookback_weeks).std())
        vol = max(vol, vol_floor)
        scores[s] = float(mom / vol)

    return pd.Series(scores).sort_values(ascending=False)


def pick_best_equity(scores: pd.Series, fallback: str) -> str:
    if scores.empty:
        return fallback
    best = scores.index[0]
    if not np.isfinite(scores.iloc[0]):
        return fallback
    return str(best)


def target_weights(
    state: RiskState,
    equity_symbol: str,
    defensive_symbol: str,
    normal_equity_weight: float,
    derisk_equity_weight: float,
) -> dict[str, float]:
    if state == RiskState.CIRCUIT_COOLDOWN:
        return {defensive_symbol: 1.0}
    if state == RiskState.DE_RISK:
        ew = float(derisk_equity_weight)
        return {equity_symbol: ew, defensive_symbol: 1.0 - ew}
    return {equity_symbol: float(normal_equity_weight)}
