"""聊天会话的用户与租户双重归属检查。"""

from __future__ import annotations

from typing import Any


def can_access_session(session: Any, user_id: object, tenant_id: object) -> bool:
    """仅当会话同时属于当前用户和当前租户时允许访问。"""
    if session is None:
        return False

    session_user_id = getattr(session, "user_id", None)
    session_tenant_id = getattr(session, "tenant_id", None)
    if session_user_id is None or session_tenant_id is None:
        return False

    return (
        str(session_user_id) == str(user_id)
        and str(session_tenant_id) == str(tenant_id)
    )
