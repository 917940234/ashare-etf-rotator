"""
认证相关路由 - /api/auth/*
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
from pathlib import Path

from auth import (
    authenticate_user, create_access_token,
    create_user, verify_password, hash_password
)
from deps import require_user


router = APIRouter(prefix="/api/auth", tags=["认证"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/register")
def api_register(req: RegisterRequest):
    """用户注册"""
    success, msg = create_user(req.username, req.password)
    if not success:
        raise HTTPException(400, msg)
    return {"message": msg}


@router.post("/login")
def api_login(req: LoginRequest):
    """用户登录"""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token({"sub": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"],
            "avatar": user.get("avatar")
        }
    }


@router.get("/me")
def api_get_me(user: dict = Depends(require_user)):
    """获取当前用户信息"""
    return {
        "id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"],
        "avatar": user.get("avatar")
    }


@router.post("/change-password")
def api_change_password(req: ChangePasswordRequest, user: dict = Depends(require_user)):
    """修改密码"""
    # 验证旧密码
    if not verify_password(req.old_password, user["password_hash"]):
        raise HTTPException(400, "当前密码错误")
    
    if len(req.new_password) < 6:
        raise HTTPException(400, "新密码至少6个字符")
    
    # 更新密码
    db_path = Path(__file__).parent.parent / "data" / "users.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    new_hash = hash_password(req.new_password)
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    conn.commit()
    conn.close()
    
    return {"message": "密码修改成功"}
