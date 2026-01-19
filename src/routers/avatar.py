"""
头像管理路由 - /api/avatar/*
"""
import base64
import hashlib
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import sqlite3

from deps import require_user
from auth import DB_PATH


router = APIRouter(prefix="/api/avatar", tags=["头像"])


# 默认头像列表（使用开源头像API，避免版权问题）
# 使用 DiceBear 的不同风格预设种子
DEFAULT_AVATARS = [
    {"id": "avatar_1", "url": "https://api.dicebear.com/7.x/adventurer/svg?seed=Felix"},
    {"id": "avatar_2", "url": "https://api.dicebear.com/7.x/adventurer/svg?seed=Luna"},
    {"id": "avatar_3", "url": "https://api.dicebear.com/7.x/adventurer/svg?seed=Max"},
    {"id": "avatar_4", "url": "https://api.dicebear.com/7.x/adventurer/svg?seed=Bella"},
    {"id": "avatar_5", "url": "https://api.dicebear.com/7.x/big-ears/svg?seed=Felix"},
    {"id": "avatar_6", "url": "https://api.dicebear.com/7.x/big-ears/svg?seed=Luna"},
    {"id": "avatar_7", "url": "https://api.dicebear.com/7.x/big-ears/svg?seed=Max"},
    {"id": "avatar_8", "url": "https://api.dicebear.com/7.x/big-ears/svg?seed=Bella"},
    {"id": "avatar_9", "url": "https://api.dicebear.com/7.x/bottts/svg?seed=Felix"},
    {"id": "avatar_10", "url": "https://api.dicebear.com/7.x/bottts/svg?seed=Luna"},
    {"id": "avatar_11", "url": "https://api.dicebear.com/7.x/bottts/svg?seed=Max"},
    {"id": "avatar_12", "url": "https://api.dicebear.com/7.x/bottts/svg?seed=Bella"},
    {"id": "avatar_13", "url": "https://api.dicebear.com/7.x/fun-emoji/svg?seed=Felix"},
    {"id": "avatar_14", "url": "https://api.dicebear.com/7.x/fun-emoji/svg?seed=Luna"},
    {"id": "avatar_15", "url": "https://api.dicebear.com/7.x/fun-emoji/svg?seed=Max"},
    {"id": "avatar_16", "url": "https://api.dicebear.com/7.x/fun-emoji/svg?seed=Bella"},
    {"id": "avatar_17", "url": "https://api.dicebear.com/7.x/lorelei/svg?seed=Felix"},
    {"id": "avatar_18", "url": "https://api.dicebear.com/7.x/lorelei/svg?seed=Luna"},
    {"id": "avatar_19", "url": "https://api.dicebear.com/7.x/pixel-art/svg?seed=Felix"},
    {"id": "avatar_20", "url": "https://api.dicebear.com/7.x/pixel-art/svg?seed=Luna"},
]


class UploadAvatarRequest(BaseModel):
    avatar_data: str  # Base64 编码的图片数据 或 URL


class SelectAvatarRequest(BaseModel):
    avatar_id: str  # 默认头像ID


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_user_avatar(user_id: int, avatar_url: str) -> bool:
    """更新用户头像"""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_url, user_id))
    conn.commit()
    conn.close()
    return True


@router.get("/defaults")
def get_default_avatars():
    """获取默认头像列表"""
    return {"avatars": DEFAULT_AVATARS}


@router.post("/select")
def select_default_avatar(req: SelectAvatarRequest, user: dict = Depends(require_user)):
    """选择默认头像"""
    avatar = next((a for a in DEFAULT_AVATARS if a["id"] == req.avatar_id), None)
    if not avatar:
        raise HTTPException(400, "无效的头像ID")
    
    update_user_avatar(user["id"], avatar["url"])
    return {"message": "头像更新成功", "avatar": avatar["url"]}


@router.post("/upload")
def upload_avatar(req: UploadAvatarRequest, user: dict = Depends(require_user)):
    """上传自定义头像（支持 Base64 或 URL）"""
    avatar_data = req.avatar_data.strip()
    
    # 检查是否为 URL
    if avatar_data.startswith("http://") or avatar_data.startswith("https://"):
        # 简单验证 URL 长度
        if len(avatar_data) > 2000:
            raise HTTPException(400, "头像 URL 过长")
        update_user_avatar(user["id"], avatar_data)
        return {"message": "头像更新成功", "avatar": avatar_data}
    
    # 检查是否为 Base64 图片
    if avatar_data.startswith("data:image/"):
        # 检查大小（约 500KB 限制）
        if len(avatar_data) > 700000:
            raise HTTPException(400, "头像图片过大，请选择小于 500KB 的图片")
        
        # 验证 Base64 格式
        try:
            header, encoded = avatar_data.split(",", 1)
            base64.b64decode(encoded)
        except Exception:
            raise HTTPException(400, "无效的图片数据")
        
        update_user_avatar(user["id"], avatar_data)
        return {"message": "头像更新成功", "avatar": avatar_data}
    
    raise HTTPException(400, "无效的头像数据格式")
