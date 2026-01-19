"""
管理员相关路由 - /api/admin/*
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import require_admin
from auth import get_all_users, delete_user
from trading import reset_account as reset_trading_account


router = APIRouter(prefix="/api/admin", tags=["管理员"])


@router.get("/users")
def api_admin_get_users(user: dict = Depends(require_admin)):
    """获取所有用户"""
    return get_all_users()


@router.post("/reset-account/{user_id}")
def api_admin_reset_account(user_id: int, admin: dict = Depends(require_admin)):
    """重置用户模拟账户"""
    reset_trading_account(user_id)
    return {"message": f"已重置用户 {user_id} 的模拟交易账户"}


@router.post("/delete-user/{user_id}")
def api_admin_delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """删除用户"""
    if user_id == admin["id"]:
        raise HTTPException(400, "不能删除自己")
    success, msg = delete_user(user_id)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}
