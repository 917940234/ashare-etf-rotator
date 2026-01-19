#!/usr/bin/env python3
"""
管理员账户初始化脚本（一次性运行）

用法：
    python init_admin.py <用户名> <密码>
    
示例：
    python init_admin.py admin MySecurePassword123
    
注意：此脚本仅需在首次部署时运行一次。
"""
import sys
import sqlite3
import hashlib
import secrets
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "users.db"


def hash_password(password: str, salt: str = None) -> str:
    """密码哈希（SHA256 + 随机盐）"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def init_admin(username: str, password: str):
    """初始化管理员账户"""
    DATA_DIR.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 创建用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            avatar TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建留言表
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            content TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(parent_id) REFERENCES messages(id)
        )
    ''')
    
    # 创建留言反应表
    c.execute('''
        CREATE TABLE IF NOT EXISTS message_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reaction_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(message_id, user_id),
            FOREIGN KEY(message_id) REFERENCES messages(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    
    # 检查是否已存在管理员
    c.execute("SELECT id, username FROM users WHERE is_admin = 1")
    existing = c.fetchone()
    if existing:
        print(f"⚠️  已存在管理员账户: {existing[1]} (ID: {existing[0]})")
        print("   如需重置，请先手动删除 data/users.db")
        conn.close()
        return False
    
    # 创建管理员
    password_hash = hash_password(password)
    c.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
        (username, password_hash)
    )
    conn.commit()
    conn.close()
    
    print(f"✅ 管理员账户创建成功！")
    print(f"   用户名: {username}")
    print(f"   数据库: {DB_PATH}")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python init_admin.py <用户名> <密码>")
        print("示例: python init_admin.py admin MySecurePassword123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    if len(username) < 2:
        print("❌ 用户名至少2个字符")
        sys.exit(1)
    if len(password) < 6:
        print("❌ 密码至少6个字符")
        sys.exit(1)
    
    success = init_admin(username, password)
    sys.exit(0 if success else 1)
