from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_rate: float
    min_commission: float
    stamp_tax_rate: float
    slippage_bps: float

    def estimate_for_rebalance(self, trades: list[dict]) -> float:
        """
        trades: [{"symbol": str, "trade_value": float, "sell_value": float}]
        佣金最低按“每个发生交易的标的”计入（保守近似）。
        """
        total = 0.0
        for t in trades:
            trade_value = float(t.get("trade_value", 0.0))
            sell_value = float(t.get("sell_value", 0.0))
            if trade_value <= 0:
                continue
            commission = max(trade_value * self.commission_rate, self.min_commission)
            stamp_tax = sell_value * self.stamp_tax_rate
            slippage = trade_value * (self.slippage_bps / 10000.0)
            total += commission + stamp_tax + slippage
        return float(total)

