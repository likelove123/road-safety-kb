"""极简登录：管理员 / 临时访客两个角色，支持访客自助注册。

- 管理员：可入库、审核、发布、废止
- 临时访客：只读，可问答与案情研判
内置账号密码来自 Streamlit secrets 或 .env，默认 admin/admin123、guest/guest123；
自助注册的账号一律为临时访客，账号存本地 SQLite（data/users.db）。
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime

import streamlit as st

import config

ROLE_NAMES = {"admin": "管理员", "guest": "临时访客"}

# 账号：1-6 位中文或英文字母
USERNAME_RE = re.compile(r"^[A-Za-z\u4e00-\u9fa5]{1,6}$")
# 密码：1-10 位英文或数字，且必须包含至少一位英文
PASSWORD_RE = re.compile(r"^[A-Za-z0-9]{1,10}$")
PASSWORD_LETTER = re.compile(r"[A-Za-z]")


def _match(value: str, expected: str) -> bool:
    return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))


def _connect() -> sqlite3.Connection:
    """打开账号库，表不存在时自动建表。"""
    config.USERS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(config.USERS_DB))
    con.execute(
        """CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'guest',
            created_at TEXT NOT NULL
        )"""
    )
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower ON users(lower(username))")
    return con


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000).hex()


def validate_username(username: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "账号名需为 1-6 位中文或英文字母"
    return None


def validate_password(password: str) -> str | None:
    if not PASSWORD_RE.match(password or ""):
        return "密码需为 1-10 位英文或数字"
    if not PASSWORD_LETTER.search(password):
        return "密码必须包含至少 1 位英文字母"
    return None


def register(username: str, password: str) -> str | None:
    """注册临时访客账号。成功返回 None，失败返回提示语。"""
    username = (username or "").strip()
    password = password or ""
    err = validate_username(username) or validate_password(password)
    if err:
        return err
    if username.lower() in {config.ADMIN_USER.lower(), config.GUEST_USER.lower()}:
        return "该账号名已被占用"

    salt = secrets.token_hex(16)
    con = _connect()
    try:
        con.execute(
            "INSERT INTO users(username, password_hash, salt, role, created_at) VALUES(?,?,?,?,?)",
            (username, _hash_password(password, salt), salt, "guest",
             datetime.now().isoformat(timespec="seconds")),
        )
        con.commit()
    except sqlite3.IntegrityError:
        return "该账号名已被注册"
    finally:
        con.close()
    return None


def _registered_user(username: str, password: str) -> dict | None:
    con = _connect()
    try:
        row = con.execute(
            "SELECT username, password_hash, salt, role FROM users WHERE lower(username)=lower(?)",
            (username,),
        ).fetchone()
    finally:
        con.close()
    if not row or not _match(_hash_password(password, row[2]), row[1]):
        return None
    return {"username": row[0], "role": row[3], "name": ROLE_NAMES.get(row[3], "临时访客")}


def authenticate(username: str, password: str) -> dict | None:
    """校验账号，成功返回用户信息。内置账号优先，其余查注册库。"""
    username = (username or "").strip()
    if _match(username, config.ADMIN_USER) and _match(password or "", config.ADMIN_PASSWORD):
        return {"username": username, "role": "admin", "name": "管理员"}
    if _match(username, config.GUEST_USER) and _match(password or "", config.GUEST_PASSWORD):
        return {"username": username, "role": "guest", "name": "临时访客"}
    return _registered_user(username, password or "")


def login(user: dict) -> None:
    st.session_state.auth_user = user


def logout() -> None:
    for key in ("auth_user", "messages", "pending_question", "case_result", "nav"):
        st.session_state.pop(key, None)


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("role") == "admin")
