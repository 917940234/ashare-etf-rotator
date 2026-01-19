"""
FastAPI 主应用 - 股债轮动系统 v0.1
"""
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import threading

from data import load_config, get_asset_info, update_universe

# 路由模块
from routers import auth, data, backtest, signal, trading, etf, admin


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 定时任务配置 ====================

def run_data_update():
    """执行数据更新任务"""
    logger.info("🔄 开始自动数据更新...")
    try:
        results = update_universe()
        success_count = sum(1 for r in results.values() if r.get("status") == "ok")
        logger.info(f"✅ 数据更新完成: {success_count}/{len(results)} 个 ETF 更新成功")
    except Exception as e:
        logger.error(f"❌ 数据更新失败: {e}")


def start_scheduler():
    """启动定时任务调度器"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        # 每天 18:00 更新数据（A股收盘后）
        scheduler.add_job(
            run_data_update,
            CronTrigger(hour=18, minute=0),
            id="daily_data_update",
            name="每日数据更新",
            replace_existing=True
        )
        scheduler.start()
        logger.info("⏰ 定时任务已启动: 每天 18:00 自动更新数据")
        return scheduler
    except ImportError:
        logger.warning("⚠️ APScheduler 未安装，跳过定时任务")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 股债轮动系统启动中...")
    
    # 启动定时任务
    scheduler = start_scheduler()
    
    # 后台线程更新数据（避免阻塞启动）
    def startup_update():
        logger.info("📊 检查数据状态...")
        run_data_update()
    
    thread = threading.Thread(target=startup_update, daemon=True)
    thread.start()
    
    yield
    
    # 关闭时执行
    if scheduler:
        scheduler.shutdown()
        logger.info("⏰ 定时任务已关闭")


# 从配置读取版本号
_cfg = load_config()
APP_VERSION = _cfg.get("version", "0.1")

app = FastAPI(title="股债轮动系统", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 注册路由 ====================

# 导入新路由
from routers import messages, leaderboard, avatar, chart

app.include_router(auth.router)
app.include_router(data.router)
app.include_router(backtest.router)
app.include_router(signal.router)
app.include_router(trading.router)
app.include_router(etf.router)
app.include_router(admin.router)
app.include_router(messages.router)
app.include_router(leaderboard.router)
app.include_router(avatar.router)
app.include_router(chart.router)


# ==================== 基础 API ====================

@app.get("/api/health")
def health():
    """健康检查"""
    return {"status": "ok", "time": datetime.now().isoformat(), "version": APP_VERSION}


@app.get("/api/config")
def get_config_api():
    """获取配置"""
    return load_config()


@app.get("/api/assets")
def get_assets():
    """获取资产信息"""
    return get_asset_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

