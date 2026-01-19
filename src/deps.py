"""
共享依赖 - 认证相关依赖注入
"""
from fastapi import Header, HTTPException, Depends
from typing import Optional

from auth import decode_token, get_user


def get_current_user(authorization: str = Header(None)) -> Optional[dict]:
    """获取当前用户（可选）"""
    if not authorization:
        return None
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            return None
    except:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return get_user(payload.get("sub"))


def require_user(authorization: str = Header(None)) -> dict:
    """要求用户登录"""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def require_admin(authorization: str = Header(None)) -> dict:
    """要求管理员权限"""
    user = require_user(authorization)
    if not user.get("is_admin"):
        raise HTTPException(403, "需要管理员权限")
    return user
