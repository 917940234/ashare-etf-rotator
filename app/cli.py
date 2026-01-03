from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from app.backtest import run_bt_backtest
from app.config import AppConfig
from app.costs import CostModel
from app.data import MarketDataStore, update_universe
from app.logging_utils import setup_logging
from app.paper import PaperAccount, _account_value, _load_prices, run_paper_once
from app.report import generate_quantstats_report
from app.utils import ensure_dir
from app.strategy import RiskGate, RiskState, compute_score, pick_best_equity, target_weights


logger = logging.getLogger(__name__)


def _build_cost_model(cfg: AppConfig) -> CostModel:
    c = cfg.get("costs")
    return CostModel(
        commission_rate=float(c["commission_rate"]),
        min_commission=float(c["min_commission"]),
        stamp_tax_rate=float(c["stamp_tax_rate"]),
        slippage_bps=float(c["slippage_bps"]),
    )


def cmd_update_data(cfg: AppConfig) -> None:
    market_dir = Path(cfg.get("data", "market_dir"))
    store = MarketDataStore(market_dir=market_dir)
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    symbols = [*equity, defensive]

    update_universe(
        store=store,
        symbols=symbols,
        start_date=str(cfg.get("data", "start_date")),
        end_date=cfg.get("data", "end_date", default=None),
        attempts=int(cfg.get("data", "retry", "attempts", default=5)),
        wait_seconds=int(cfg.get("data", "retry", "wait_seconds", default=2)),
    )


def cmd_run_backtest(cfg: AppConfig) -> None:
    market_dir = Path(cfg.get("data", "market_dir"))
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    cost_model = _build_cost_model(cfg)

    out = run_bt_backtest(
        market_dir=market_dir,
        equity_etfs=equity,
        defensive_etf=defensive,
        initial_capital=float(cfg.get("project", "initial_capital")),
        no_trade_band=float(cfg.get("project", "no_trade_band")),
        momentum_lookback_days=int(cfg.get("signal", "momentum_lookback_days")),
        vol_lookback_weeks=int(cfg.get("signal", "vol_lookback_weeks")),
        vol_floor=float(cfg.get("signal", "vol_floor")),
        risk_gate_cfg=dict(cfg.get("risk_gate")),
        allocation_cfg=dict(cfg.get("allocation")),
        cost_model=cost_model,
    )

    reb_csv = Path(cfg.get("report", "backtest_rebalances_csv"))
    ensure_dir(reb_csv.parent)
    out.rebalance_records.to_csv(reb_csv, index=False, encoding="utf-8-sig")
    logger.info("保存回测再平衡记录：%s", reb_csv)

    eq_path = Path(cfg.get("report", "backtest_equity_parquet"))
    ensure_dir(eq_path.parent)
    out.equity_curve.to_frame("equity").to_parquet(eq_path, index=True)
    logger.info("保存回测净值曲线：%s", eq_path)

    html = Path(cfg.get("report", "backtest_html"))
    generate_quantstats_report(out.equity_curve, html, title="ETF Rotator Backtest (cost-adjusted approx)")
    logger.info("回测统计：%s", out.stats)


def cmd_run_paper(cfg: AppConfig) -> None:
    market_dir = Path(cfg.get("data", "market_dir"))
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    cost_model = _build_cost_model(cfg)

    blotter, equity_curve = run_paper_once(
        market_dir=market_dir,
        equity_etfs=equity,
        defensive_etf=defensive,
        account_path=Path(cfg.get("paper", "account_path")),
        blotter_dir=Path(cfg.get("paper", "blotter_dir")),
        initial_capital=float(cfg.get("project", "initial_capital")),
        no_trade_band=float(cfg.get("project", "no_trade_band")),
        momentum_lookback_days=int(cfg.get("signal", "momentum_lookback_days")),
        vol_lookback_weeks=int(cfg.get("signal", "vol_lookback_weeks")),
        vol_floor=float(cfg.get("signal", "vol_floor")),
        risk_gate_cfg=dict(cfg.get("risk_gate")),
        allocation_cfg=dict(cfg.get("allocation")),
        cost_model=cost_model,
    )
    html = Path(cfg.get("report", "paper_html"))
    generate_quantstats_report(equity_curve, html, title="ETF Rotator Paper Trading")
    eq_path = Path(cfg.get("report", "paper_equity_parquet"))
    ensure_dir(eq_path.parent)
    equity_curve.to_frame("equity").to_parquet(eq_path, index=True)
    logger.info("保存纸交易净值曲线：%s", eq_path)
    logger.info("纸交易完成：最新净值 %.2f（点数=%d）", float(equity_curve.iloc[-1]), len(equity_curve))


def cmd_generate_report(cfg: AppConfig, source: str) -> None:
    source = source.lower()
    if source not in {"backtest", "paper"}:
        raise ValueError("generate-report --source 只能是 backtest 或 paper")

    if source == "backtest":
        eq_path = Path(cfg.get("report", "backtest_equity_parquet"))
        out_html = Path(cfg.get("report", "backtest_html"))
        title = "ETF Rotator Backtest (from cached equity)"
    else:
        eq_path = Path(cfg.get("report", "paper_equity_parquet"))
        out_html = Path(cfg.get("report", "paper_html"))
        title = "ETF Rotator Paper Trading (from cached equity)"

    if not eq_path.exists():
        raise FileNotFoundError(f"缺少净值缓存：{eq_path}（请先运行 run-backtest 或 run-paper）")
    df = pd.read_parquet(eq_path)
    equity = df["equity"]
    generate_quantstats_report(equity, out_html, title=title)


def cmd_plan_weekly(cfg: AppConfig) -> None:
    """
    周五（或本周最后一个交易日）收盘后生成“下个交易日调仓计划”：
    - 仅用最新收盘价作为参考价，不做虚拟成交、不更新纸账户
    - 风控闸门使用纸账户的净值峰值与历史估值（至 signal_date）评估
    """
    market_dir = Path(cfg.get("data", "market_dir"))
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    symbols = list(dict.fromkeys([*equity, defensive]))

    account_path = Path(cfg.get("paper", "account_path"))
    if account_path.exists():
        account = PaperAccount.load(account_path)
        logger.info("加载纸交易账户：%s", account_path)
    else:
        gate_state = {"state": RiskState.NORMAL.value, "cooldown_left": 0}
        account = PaperAccount.new(
            initial_capital=float(cfg.get("project", "initial_capital")),
            gate_state=gate_state,
        )
        logger.info("纸交易账户不存在，使用初始账户进行计划（不落盘）")

    prices = _load_prices(market_dir, symbols)
    signal_dt = pd.Timestamp(prices.index[-1])
    px_signal = prices.loc[signal_dt]

    gate = RiskGate(**dict(cfg.get("risk_gate")))
    gate.state = RiskState(account.gate.get("state", RiskState.NORMAL.value))
    gate.cooldown_left = int(account.gate.get("cooldown_left", 0))

    # 用 signal_dt 的估值更新 peak（不落盘）
    signal_value = _account_value(account, px_signal)
    equity_peak = max(float(account.equity_peak), float(signal_value))
    drawdown = 1.0 - signal_value / equity_peak if equity_peak > 0 else 0.0
    state, _ = gate.on_rebalance(drawdown)

    scores = compute_score(
        prices=prices,
        symbols=equity,
        signal_date=signal_dt,
        momentum_lookback_days=int(cfg.get("signal", "momentum_lookback_days")),
        vol_lookback_weeks=int(cfg.get("signal", "vol_lookback_weeks")),
        vol_floor=float(cfg.get("signal", "vol_floor")),
    )
    winner = pick_best_equity(scores, fallback=equity[0])
    tw = target_weights(
        state=state,
        equity_symbol=winner,
        defensive_symbol=defensive,
        normal_equity_weight=float(cfg.get("allocation", "normal_equity_weight")),
        derisk_equity_weight=float(cfg.get("allocation", "derisk_equity_weight")),
    )

    # 输出计划CSV（便于周一手动下单）
    rows = []
    for s in symbols:
        rows.append(
            {
                "signal_date": signal_dt.strftime("%Y-%m-%d"),
                "planned_trade_date": "",
                "symbol": s,
                "target_weight": float(tw.get(s, 0.0)),
                "reference_price": float(px_signal.get(s)),
                "state": state.value,
                "winner_equity": winner,
                "drawdown": float(drawdown),
                "equity_estimated": float(signal_value),
            }
        )
    plan_df = pd.DataFrame(rows)
    out_csv = Path(cfg.get("paper", "blotter_dir")) / f"weekly_plan_{signal_dt.strftime('%Y%m%d')}.csv"
    ensure_dir(out_csv.parent)
    plan_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    logger.info("生成周频计划：%s（state=%s winner=%s drawdown=%.2f%%）",
                out_csv, state.value, winner, drawdown * 100.0)
    print(plan_df.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="ashare-etf-rotator")
    parser.add_argument("--config", default="config/config.yaml", help="配置文件路径")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("update-data", help="使用AKShare更新ETF日线到本地Parquet")
    sub.add_parser("run-backtest", help="运行bt回测并生成quantstats报告")
    sub.add_parser("run-paper", help="运行一次纸交易（执行下一次周频调仓）")
    sub.add_parser("plan-weekly", help="生成下周调仓计划（不虚拟成交、不更新纸账户）")
    p = sub.add_parser("generate-report", help="从已缓存净值曲线生成/重生成报告")
    p.add_argument("--source", required=True, choices=["backtest", "paper"])

    args = parser.parse_args()
    cfg = AppConfig.load(args.config)
    setup_logging(
        log_path=str(cfg.get("logging", "log_path")),
        level=str(cfg.get("logging", "level", default="INFO")),
    )

    try:
        if args.cmd == "update-data":
            cmd_update_data(cfg)
        elif args.cmd == "run-backtest":
            cmd_run_backtest(cfg)
        elif args.cmd == "run-paper":
            cmd_run_paper(cfg)
        elif args.cmd == "plan-weekly":
            cmd_plan_weekly(cfg)
        elif args.cmd == "generate-report":
            cmd_generate_report(cfg, source=args.source)
        else:
            raise ValueError(f"未知命令：{args.cmd}")
    except Exception:
        logger.exception("执行失败：%s", args.cmd)
        raise


if __name__ == "__main__":
    main()
