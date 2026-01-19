"""
留言墙路由 - /api/messages/*
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from deps import require_user
from auth import DB_PATH


router = APIRouter(prefix="/api/messages", tags=["留言墙"])


class CreateMessageRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None


class ReactionRequest(BaseModel):
    reaction_type: str  # 'like' or 'dislike'


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("")
def get_messages(page: int = 1, page_size: int = 20, user: dict = Depends(require_user)):
    """获取留言列表（分页，包含用户反应状态）"""
    conn = get_db()
    c = conn.cursor()
    
    offset = (page - 1) * page_size
    
    # 获取顶级留言（非回复）
    c.execute('''
        SELECT m.id, m.user_id, m.content, m.likes, m.dislikes, m.created_at, m.parent_id,
               u.username, u.avatar
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.parent_id IS NULL
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
    ''', (page_size, offset))
    
    messages = []
    for row in c.fetchall():
        msg = dict(row)
        
        # 获取用户对该消息的反应
        c.execute('''
            SELECT reaction_type FROM message_reactions
            WHERE message_id = ? AND user_id = ?
        ''', (msg['id'], user['id']))
        reaction_row = c.fetchone()
        msg['user_reaction'] = reaction_row['reaction_type'] if reaction_row else None
        
        # 获取该消息的回复
        c.execute('''
            SELECT m.id, m.user_id, m.content, m.likes, m.dislikes, m.created_at,
                   u.username, u.avatar
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.parent_id = ?
            ORDER BY m.created_at ASC
        ''', (msg['id'],))
        
        replies = []
        for reply_row in c.fetchall():
            reply = dict(reply_row)
            # 获取用户对回复的反应
            c.execute('''
                SELECT reaction_type FROM message_reactions
                WHERE message_id = ? AND user_id = ?
            ''', (reply['id'], user['id']))
            reply_reaction = c.fetchone()
            reply['user_reaction'] = reply_reaction['reaction_type'] if reply_reaction else None
            replies.append(reply)
        
        msg['replies'] = replies
        messages.append(msg)
    
    # 获取总数
    c.execute('SELECT COUNT(*) FROM messages WHERE parent_id IS NULL')
    total = c.fetchone()[0]
    
    conn.close()
    
    return {
        'messages': messages,
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': (total + page_size - 1) // page_size
    }


@router.post("")
def create_message(req: CreateMessageRequest, user: dict = Depends(require_user)):
    """发布留言或回复"""
    if not req.content or len(req.content.strip()) == 0:
        raise HTTPException(400, "留言内容不能为空")
    if len(req.content) > 500:
        raise HTTPException(400, "留言内容不能超过500字")
    
    conn = get_db()
    c = conn.cursor()
    
    # 如果是回复，检查父留言是否存在
    if req.parent_id:
        c.execute('SELECT id FROM messages WHERE id = ?', (req.parent_id,))
        if not c.fetchone():
            conn.close()
            raise HTTPException(404, "要回复的留言不存在")
    
    c.execute('''
        INSERT INTO messages (user_id, content, parent_id, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user['id'], req.content.strip(), req.parent_id, datetime.now().isoformat()))
    
    message_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {'message': '发布成功', 'id': message_id}


@router.post("/{message_id}/react")
def react_to_message(message_id: int, req: ReactionRequest, user: dict = Depends(require_user)):
    """对留言点赞/踩（同一用户只能选一个，再次点击取消）"""
    if req.reaction_type not in ('like', 'dislike'):
        raise HTTPException(400, "无效的反应类型")
    
    conn = get_db()
    c = conn.cursor()
    
    # 检查留言是否存在
    c.execute('SELECT id, likes, dislikes FROM messages WHERE id = ?', (message_id,))
    msg = c.fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, "留言不存在")
    
    # 检查用户是否已有反应
    c.execute('''
        SELECT reaction_type FROM message_reactions
        WHERE message_id = ? AND user_id = ?
    ''', (message_id, user['id']))
    existing = c.fetchone()
    
    likes = msg['likes']
    dislikes = msg['dislikes']
    new_reaction = None
    
    if existing:
        old_type = existing['reaction_type']
        # 删除旧的反应
        c.execute('''
            DELETE FROM message_reactions WHERE message_id = ? AND user_id = ?
        ''', (message_id, user['id']))
        
        # 更新计数
        if old_type == 'like':
            likes -= 1
        else:
            dislikes -= 1
        
        # 如果点击的是不同类型，添加新反应
        if old_type != req.reaction_type:
            c.execute('''
                INSERT INTO message_reactions (message_id, user_id, reaction_type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (message_id, user['id'], req.reaction_type, datetime.now().isoformat()))
            
            if req.reaction_type == 'like':
                likes += 1
            else:
                dislikes += 1
            new_reaction = req.reaction_type
    else:
        # 添加新反应
        c.execute('''
            INSERT INTO message_reactions (message_id, user_id, reaction_type, created_at)
            VALUES (?, ?, ?, ?)
        ''', (message_id, user['id'], req.reaction_type, datetime.now().isoformat()))
        
        if req.reaction_type == 'like':
            likes += 1
        else:
            dislikes += 1
        new_reaction = req.reaction_type
    
    # 更新留言的点赞/踩计数
    c.execute('''
        UPDATE messages SET likes = ?, dislikes = ? WHERE id = ?
    ''', (likes, dislikes, message_id))
    
    conn.commit()
    conn.close()
    
    return {
        'message': '操作成功',
        'likes': likes,
        'dislikes': dislikes,
        'user_reaction': new_reaction
    }


@router.delete("/{message_id}")
def delete_message(message_id: int, user: dict = Depends(require_user)):
    """删除留言（仅作者或管理员可删除）"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT user_id FROM messages WHERE id = ?', (message_id,))
    msg = c.fetchone()
    
    if not msg:
        conn.close()
        raise HTTPException(404, "留言不存在")
    
    if msg['user_id'] != user['id'] and not user.get('is_admin'):
        conn.close()
        raise HTTPException(403, "无权删除此留言")
    
    # 删除相关反应
    c.execute('DELETE FROM message_reactions WHERE message_id = ?', (message_id,))
    # 删除留言（包括回复）
    c.execute('DELETE FROM messages WHERE id = ? OR parent_id = ?', (message_id, message_id))
    
    conn.commit()
    conn.close()
    
    return {'message': '删除成功'}
