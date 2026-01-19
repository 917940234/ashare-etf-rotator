"""
ETF 管理相关路由 - /api/etf/*
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from deps import require_admin
from etf_manager import search_etf, fetch_etf_info, add_asset, remove_asset, update_all_names, get_all_assets


router = APIRouter(prefix="/api/etf", tags=["ETF管理"])


class AddAssetRequest(BaseModel):
    code: str
    name: Optional[str] = None
    asset_type: Optional[str] = None
    weight: Optional[float] = None
    desc: Optional[str] = None


@router.get("/search")
def api_search_etf(keyword: str, admin: dict = Depends(require_admin)):
    """搜索 ETF"""
    return search_etf(keyword)


@router.get("/info/{code}")
def api_get_etf_info(code: str):
    """获取单个 ETF 信息"""
    return fetch_etf_info(code)


@router.post("/add")
def api_add_asset(req: AddAssetRequest, admin: dict = Depends(require_admin)):
    """添加 ETF 到资产池"""
    success, msg = add_asset(req.asset_type, req.code, req.name, req.weight, req.desc)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}


@router.post("/remove/{code}")
def api_remove_asset(code: str, admin: dict = Depends(require_admin)):
    """从资产池移除 ETF"""
    success, msg = remove_asset(code)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}


@router.post("/update-names")
def api_update_etf_names(admin: dict = Depends(require_admin)):
    """批量联网更新所有 ETF 名称"""
    return update_all_names()


@router.get("/pool")
def api_get_asset_pool():
    """获取当前资产池"""
    return get_all_assets()
