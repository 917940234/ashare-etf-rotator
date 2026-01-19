"""
用户认证模块 - JWT + SQLite (v0.1 安全版)
敏感信息通过环境变量配置，解决 GitGuardian 安全警告
"""
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from jose import JWTError, jwt

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "users.db"

# JWT 配置（生产环境应从环境变量读取）
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "ashare-etf-rotator-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# 管理员账户（从环境变量读取）
ADMIN_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("AUTH_PASSWORD", "")


def hash_password(password: str, salt: str = None) -> str:
    """密码哈希（SHA256 + 随机盐）"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(plain_password: str, stored_password: str) -> bool:
    """验证密码（仅支持 salt$hash 格式）"""
    if '$' not in stored_password:
        return False  # 不再兼容旧格式
    salt, _ = stored_password.split('$', 1)
    return hash_password(plain_password, salt) == stored_password


def init_db():
    """初始化数据库"""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
    
    # 创建留言表（支持回复、点赞/踩）
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
    
    # 创建留言反应表（防止重复点赞/踩）
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
    
    # 升级旧表结构
    try:
        c.execute("ALTER TABLE messages ADD COLUMN parent_id INTEGER DEFAULT NULL")
        conn.commit()
    except:
        pass
    try:
        c.execute("ALTER TABLE messages ADD COLUMN likes INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass
    try:
        c.execute("ALTER TABLE messages ADD COLUMN dislikes INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass
    
    # 确保新字段存在（升级旧数据库）
    try:
        c.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
        conn.commit()
    except:
        pass  # 字段已存在
    
    # 确保管理员存在
    c.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,))
    if not c.fetchone():
        password_hash = hash_password(ADMIN_PASSWORD)
        c.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            (ADMIN_USERNAME, password_hash)
        )
        conn.commit()
    
    conn.close()


def get_user(username: str) -> Optional[dict]:
    """获取用户"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, is_admin, avatar FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "is_admin": bool(row[3]),
            "avatar": row[4] or _generate_default_avatar(row[1])
        }
    return None


def _generate_default_avatar(username: str) -> str:
    """生成默认头像 URL（使用 DiceBear API）"""
    import hashlib
    seed = hashlib.md5(username.encode()).hexdigest()
    return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"


def create_user(username: str, password: str) -> tuple[bool, str]:
    """创建用户"""
    if len(username) < 2:
        return False, "用户名至少2个字符"
    if len(password) < 6:
        return False, "密码至少6个字符"
    
    if get_user(username):
        return False, "用户名已存在"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        password_hash = hash_password(password)
        c.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        return True, "注册成功"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """认证用户"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """创建 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_all_users() -> list:
    """获取所有用户（管理员用）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin, created_at FROM users")
    rows = c.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "username": r[1], "is_admin": bool(r[2]), "created_at": r[3]}
        for r in rows
    ]


def delete_user(user_id: int) -> tuple[bool, str]:
    """删除用户"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 检查用户是否存在且非管理员
    c.execute("SELECT username, is_admin FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"
    if row[1]:  # is_admin
        conn.close()
        return False, "不能删除管理员"
    
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, f"用户 {row[0]} 已删除"


# 初始化数据库
init_db()

