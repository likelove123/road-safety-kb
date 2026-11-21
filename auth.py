"""极简登录：管理员 / 临时访客两个角色。

- 管理员：可入库、审核、发布、废止
- 临时访客：只读，可问答与案情研判
账号密码来自 Streamlit secrets 或 .env，默认 admin/admin123、guest/guest123。
"""
import hmac

import streamlit as st

import config

ROLE_NAMES = {"admin": "管理员", "guest": "临时访客"}


def _match(value: str, expected: str) -> bool:
    return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))


def authenticate(username: str, password: str) -> dict | None:
    """校验账号，成功返回用户信息。"""
    username = (username or "").strip()
    if _match(username, config.ADMIN_USER) and _match(password or "", config.ADMIN_PASSWORD):
        return {"username": username, "role": "admin", "name": "管理员"}
    if _match(username, config.GUEST_USER) and _match(password or "", config.GUEST_PASSWORD):
        return {"username": username, "role": "guest", "name": "临时访客"}
    return None


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
