from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

from core.backtest import run_bt_backtest
from core.config import AppConfig
from core.costs import CostModel
from core.data import MarketDataStore, update_universe
from core.logging_utils import setup_logging
from core.paper import PaperAccount, _account_value, _load_prices, run_paper_once
from core.report import generate_quantstats_report
from core.strategy import RiskGate, RiskState, compute_score, pick_best_equity, target_weights
from core.utils import ensure_dir

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/config.yaml")

# ====== 固定账号（不允许注册）======
AUTH_USERNAME = "永恒的谜团"
_PWD_SALT_B64 = "YXNoYXJlLWV0Zi1yb3RhdG9yOjpmaXhlZC1zYWx0OjoyMDI2"
_PWD_HASH_B64 = "St0zr5pEIgkRXOZ1bs5RZlGKCl4pvz55wX/J7ITjz5w="
_PWD_ITER = 200_000

# 用于 SessionCookie 签名（写死）
SESSION_SECRET = "ashare-etf-rotator::session::fixed-secret::2026"


def _verify_password(password: str) -> bool:
    salt = base64.b64decode(_PWD_SALT_B64)
    expected = base64.b64decode(_PWD_HASH_B64)
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PWD_ITER)
    return hmac.compare_digest(got, expected)


def _require_auth(req: Request) -> None:
    if not bool(req.session.get("authed")):
        raise HTTPException(status_code=401, detail="未登录")


def _load_cfg() -> AppConfig:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=500, detail=f"缺少配置文件：{CONFIG_PATH}")
    return AppConfig.load(CONFIG_PATH)


def _build_cost_model(cfg: AppConfig) -> CostModel:
    c = cfg.get("costs")
    return CostModel(
        commission_rate=float(c["commission_rate"]),
        min_commission=float(c["min_commission"]),
        stamp_tax_rate=float(c["stamp_tax_rate"]),
        slippage_bps=float(c["slippage_bps"]),
    )


TaskKind = Literal["update-data", "run-backtest", "plan-weekly", "run-paper"]


@dataclass
class Task:
    id: str
    kind: TaskKind
    status: Literal["pending", "running", "success", "failed"] = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    message: str = ""
    error: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)


_tasks_lock = threading.Lock()
_tasks: dict[str, Task] = {}
_futures: dict[str, Future] = {}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")


def _run_task(task: Task) -> None:
    cfg = _load_cfg()
    setup_logging(
        log_path=str(cfg.get("logging", "log_path")),
        level=str(cfg.get("logging", "level", default="INFO")),
    )

    task.started_at = time.time()
    task.status = "running"
    try:
        if task.kind == "update-data":
            _task_update_data(cfg, task)
        elif task.kind == "run-backtest":
            _task_run_backtest(cfg, task)
        elif task.kind == "plan-weekly":
            _task_plan_weekly(cfg, task)
        elif task.kind == "run-paper":
            _task_run_paper(cfg, task)
        else:
            raise RuntimeError(f"未知任务类型：{task.kind}")

        task.status = "success"
        task.message = "完成"
    except Exception as e:
        logger.exception("任务失败：%s", task.kind)
        task.status = "failed"
        task.error = repr(e)
        task.message = "失败"
    finally:
        task.finished_at = time.time()


def _enqueue(kind: TaskKind) -> Task:
    task_id = uuid.uuid4().hex
    task = Task(id=task_id, kind=kind)
    with _tasks_lock:
        _tasks[task_id] = task
        _futures[task_id] = _executor.submit(_run_task, task)
    return task


def _task_update_data(cfg: AppConfig, task: Task) -> None:
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
    task.outputs = {"symbols": symbols}


def _task_run_backtest(cfg: AppConfig, task: Task) -> None:
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

    eq_path = Path(cfg.get("report", "backtest_equity_parquet"))
    ensure_dir(eq_path.parent)
    out.equity_curve.to_frame("equity").to_parquet(eq_path, index=True)

    html = Path(cfg.get("report", "backtest_html"))
    generate_quantstats_report(out.equity_curve, html, title="ETF Rotator Backtest (cost-adjusted approx)")

    task.outputs = {
        "stats": out.stats,
        "artifacts": [str(reb_csv), str(eq_path), str(html)],
    }


def _task_plan_weekly(cfg: AppConfig, task: Task) -> None:
    market_dir = Path(cfg.get("data", "market_dir"))
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    symbols = list(dict.fromkeys([*equity, defensive]))

    account_path = Path(cfg.get("paper", "account_path"))
    if account_path.exists():
        account = PaperAccount.load(account_path)
    else:
        gate_state = {"state": RiskState.NORMAL.value, "cooldown_left": 0}
        account = PaperAccount.new(
            initial_capital=float(cfg.get("project", "initial_capital")),
            gate_state=gate_state,
        )

    prices = _load_prices(market_dir, symbols)
    signal_dt = pd.Timestamp(prices.index[-1])
    px_signal = prices.loc[signal_dt]

    gate = RiskGate(**dict(cfg.get("risk_gate")))
    gate.state = RiskState(account.gate.get("state", RiskState.NORMAL.value))
    gate.cooldown_left = int(account.gate.get("cooldown_left", 0))

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

    task.outputs = {"artifact": str(out_csv), "state": state.value, "winner": winner}


def _task_run_paper(cfg: AppConfig, task: Task) -> None:
    market_dir = Path(cfg.get("data", "market_dir"))
    equity = list(cfg.get("universe", "equity_etfs"))
    defensive = str(cfg.get("universe", "defensive_etf"))
    cost_model = _build_cost_model(cfg)

    try:
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
    except RuntimeError as e:
        if "账户已是最新" in str(e):
            task.outputs = {"message": "无需更新（账户已是最新）"}
            return
        raise

    html = Path(cfg.get("report", "paper_html"))
    generate_quantstats_report(equity_curve, html, title="ETF Rotator Paper Trading")

    eq_path = Path(cfg.get("report", "paper_equity_parquet"))
    ensure_dir(eq_path.parent)
    equity_curve.to_frame("equity").to_parquet(eq_path, index=True)

    task.outputs = {
        "artifacts": [str(html), str(eq_path)],
        "blotter_preview": json.loads(blotter.head(50).to_json(orient="records")),
    }


def _safe_tail_log(path: Path, lines: int) -> str:
    if lines <= 0:
        return ""
    if not path.exists():
        return ""
    with path.open("rb") as f:
        data = f.read()
    text = data.decode("utf-8", errors="replace").splitlines()
    return "\n".join(text[-lines:])


def _list_reports(report_dir: Path) -> list[dict[str, Any]]:
    if not report_dir.exists():
        return []
    items = []
    for p in sorted(report_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        items.append(
            {
                "name": p.name,
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
            }
        )
    return items


app = FastAPI(title="AShare ETF Rotator API")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=False, same_site="lax")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/api/auth/login")
def login(payload: dict[str, str] = Body(...), req: Request = None) -> dict[str, Any]:
    username = payload.get("username", "")
    password = payload.get("password", "")
    if username != AUTH_USERNAME or not _verify_password(password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    assert req is not None
    req.session["authed"] = True
    req.session["user"] = AUTH_USERNAME
    return {"ok": True, "user": AUTH_USERNAME}


@app.post("/api/auth/logout")
def logout(req: Request) -> dict[str, Any]:
    req.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
def me(req: Request) -> dict[str, Any]:
    if not bool(req.session.get("authed")):
        return {"authed": False}
    return {"authed": True, "user": req.session.get("user")}


@app.get("/api/config")
def get_config(req: Request) -> dict[str, Any]:
    _require_auth(req)
    return {"path": str(CONFIG_PATH), "yaml": CONFIG_PATH.read_text(encoding="utf-8")}


@app.put("/api/config")
def put_config(req: Request, payload: dict[str, str] = Body(...)) -> dict[str, Any]:
    _require_auth(req)
    yaml_text = payload.get("yaml", "")
    if not yaml_text.strip():
        raise HTTPException(status_code=400, detail="配置内容为空")
    # 轻度校验：能被加载
    try:
        import yaml as _yaml

        _yaml.safe_load(yaml_text)
    except Exception:
        raise HTTPException(status_code=400, detail="YAML格式错误")

    backup = CONFIG_PATH.with_suffix(".yaml.bak")
    if CONFIG_PATH.exists():
        backup.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    CONFIG_PATH.write_text(yaml_text, encoding="utf-8")
    return {"ok": True, "backup": str(backup)}


@app.post("/api/tasks/{kind}")
def create_task(kind: TaskKind, req: Request) -> dict[str, Any]:
    _require_auth(req)
    task = _enqueue(kind)
    return {"task_id": task.id}


@app.get("/api/tasks")
def list_tasks(req: Request) -> dict[str, Any]:
    _require_auth(req)
    with _tasks_lock:
        items = [
            {
                "id": t.id,
                "kind": t.kind,
                "status": t.status,
                "message": t.message,
                "created_at": t.created_at,
                "started_at": t.started_at,
                "finished_at": t.finished_at,
            }
            for t in _tasks.values()
        ]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"tasks": items[:50]}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, req: Request) -> dict[str, Any]:
    _require_auth(req)
    with _tasks_lock:
        t = _tasks.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": t.id,
        "kind": t.kind,
        "status": t.status,
        "message": t.message,
        "error": t.error,
        "created_at": t.created_at,
        "started_at": t.started_at,
        "finished_at": t.finished_at,
        "outputs": t.outputs,
    }


@app.get("/api/artifacts")
def list_artifacts(req: Request) -> dict[str, Any]:
    _require_auth(req)
    cfg = _load_cfg()
    items = _list_reports(Path(cfg.get("paper", "blotter_dir")))
    return {"artifacts": items}


@app.get("/api/artifacts/{name}")
def get_artifact(name: str, req: Request):
    _require_auth(req)
    cfg = _load_cfg()
    base = Path(cfg.get("paper", "blotter_dir")).resolve()
    p = (base / name).resolve()
    if base not in p.parents and p != base:
        raise HTTPException(status_code=400, detail="非法路径")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p)


@app.get("/api/logs/tail")
def tail_logs(lines: int = 300, req: Request = None) -> PlainTextResponse:
    assert req is not None
    _require_auth(req)
    cfg = _load_cfg()
    log_path = Path(cfg.get("logging", "log_path"))
    text = _safe_tail_log(log_path, lines=min(max(int(lines), 1), 2000))
    return PlainTextResponse(text)
