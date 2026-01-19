"""
数据更新相关路由 - /api/data/*
"""
from fastapi import APIRouter, BackgroundTasks

from data import update_universe, get_data_status, get_last_update_time


router = APIRouter(prefix="/api/data", tags=["数据"])


@router.post("/update")
def api_update_data(background_tasks: BackgroundTasks):
    """触发数据更新（后台任务）"""
    background_tasks.add_task(update_universe)
    return {"status": "started"}


@router.get("/status")
def api_data_status():
    """获取数据状态（含更新时间）"""
    status = get_data_status()
    update_info = get_last_update_time()
    return {
        "etf_status": status,
        "last_update": update_info.get("last_update"),
        "updated_by": update_info.get("updated_by")
    }
