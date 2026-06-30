from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings
from app.core.database import execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import Permission, UserStatus
from app.core.exceptions import BusinessError
from app.repositories.common import audit, paginate
from app.services.permission_service import (
    normalize_permissions,
    permissions_for_user,
    require_business_scope,
    require_editable_user,
    require_permissions,
)


def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "uid": user["uid"],
        "name": user["name"],
        "email": user["email"],
        "status": user["status"],
        "permissions": permissions_for_user(user["id"]),
    }


def serialize_business_user_option(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "permissions": [
            permission
            for permission in permissions_for_user(user["id"])
            if permission in {Permission.INSPECTION_ENGINEER, Permission.PROJECT_ADMIN}
        ],
    }


def login(payload: dict[str, Any]) -> dict[str, Any]:
    user = query_one("SELECT * FROM users WHERE uid = ?", (payload.get("uid"),))
    if not user or user["status"] != UserStatus.ACTIVE:
        raise BusinessError("INVALID_UID", "UID 不存在或已停用", 401)
    if payload.get("password") not in (user["uid"], "admin"):
        raise BusinessError("INVALID_PASSWORD", "密码无效", 401)
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + timedelta(seconds=7200)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"access_token": token, "token_type": "Bearer", "expires_in": 7200, "user": serialize_user(user)}


def list_users(keyword: str | None, status: str | None, permission: str | None, page: int, page_size: int, actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    rows = query_all("SELECT * FROM users ORDER BY id")
    if status and status not in {status.value for status in UserStatus}:
        raise BusinessError("INVALID_USER_STATUS", f"未知用户状态 {status}")
    rows = [row for row in rows if row["status"] != UserStatus.DELETED]
    if keyword:
        rows = [row for row in rows if keyword in row["uid"] or keyword in row["name"] or keyword in (row["email"] or "")]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if permission:
        if permission not in {item.value for item in Permission}:
            raise BusinessError("INVALID_PERMISSION", f"未知权限 {permission}")
        rows = [row for row in rows if permission in permissions_for_user(row["id"])]
    return paginate([serialize_user(row) for row in rows], page, page_size)


def list_business_user_options(actor: dict[str, Any]) -> dict[str, Any]:
    require_business_scope(actor)
    rows = query_all("SELECT * FROM users WHERE status = ? ORDER BY id", (UserStatus.ACTIVE,))
    options = []
    for row in rows:
        option = serialize_business_user_option(row)
        if option["permissions"]:
            options.append(option)
    return {"items": options}


def ensure_not_current_user(target_user_id: int, actor_user_id: int, message: str) -> None:
    if target_user_id == actor_user_id:
        raise BusinessError("CURRENT_USER_PROTECTED", message)


def ensure_permission_admin_remains(
    target_user_id: int,
    target_status: str | None = None,
    target_permissions: list[str] | None = None,
) -> None:
    target = require_editable_user(target_user_id)
    next_status = target_status or target["status"]
    next_permissions = set(target_permissions if target_permissions is not None else permissions_for_user(target_user_id))
    if next_status == UserStatus.ACTIVE and Permission.SUPER_ADMIN in next_permissions:
        return

    rows = query_all(
        """
        SELECT u.id FROM users u
        JOIN user_permissions p ON p.user_id = u.id
        WHERE u.status = ? AND p.permission_code = ? AND u.id != ?
        """,
        (UserStatus.ACTIVE, Permission.SUPER_ADMIN, target_user_id),
    )
    if not rows:
        raise BusinessError("LAST_PERMISSION_ADMIN", "系统需保留至少一个权限管理员")


def replace_user_permissions(target_user_id: int, permissions: list[str]) -> None:
    execute("DELETE FROM user_permissions WHERE user_id = ?", (target_user_id,))
    for permission in permissions:
        execute("INSERT INTO user_permissions(user_id, permission_code) VALUES (?, ?)", (target_user_id, permission))


def create_user(payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    status = payload.get("status", UserStatus.ACTIVE)
    if status not in {UserStatus.ACTIVE, UserStatus.DISABLED}:
        raise BusinessError("INVALID_USER_STATUS", "新增账号状态只能为启用或停用")
    permissions = normalize_permissions(payload.get("permissions", []))
    cur = execute(
        "INSERT INTO users(uid, name, email, status) VALUES (?, ?, ?, ?)",
        (payload["uid"], payload["name"], payload.get("email"), status),
    )
    user_id = cur.lastrowid
    replace_user_permissions(user_id, permissions)
    audit("create_user", "user", user_id, actor["id"], payload)
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def update_user(user_id: int, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    status = payload.get("status", UserStatus.ACTIVE)
    if status not in {UserStatus.ACTIVE, UserStatus.DISABLED}:
        raise BusinessError("INVALID_USER_STATUS", "账号状态只能为启用或停用")
    permissions = normalize_permissions(payload.get("permissions", []))
    if user_id == actor["id"] and Permission.SUPER_ADMIN not in permissions:
        raise BusinessError("CURRENT_PERMISSION_ADMIN_PROTECTED", "不能取消自己的权限管理权限")
    if user_id == actor["id"] and status != UserStatus.ACTIVE:
        raise BusinessError("CURRENT_USER_PROTECTED", "不能停用当前登录账号")
    ensure_permission_admin_remains(user_id, status, permissions)
    with transaction():
        execute(
            "UPDATE users SET name = ?, email = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload["name"], payload.get("email"), status, user_id),
        )
        replace_user_permissions(user_id, permissions)
        audit("update_user", "user", user_id, actor["id"], payload)
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def update_user_permissions(user_id: int, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    permissions = normalize_permissions(payload.get("permissions", []))
    if user_id == actor["id"] and Permission.SUPER_ADMIN not in permissions:
        raise BusinessError("CURRENT_PERMISSION_ADMIN_PROTECTED", "不能取消自己的权限管理权限")
    ensure_permission_admin_remains(user_id, target_permissions=permissions)
    replace_user_permissions(user_id, permissions)
    audit("update_user_permissions", "user", user_id, actor["id"], payload)
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def disable_user(user_id: int, actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    ensure_not_current_user(user_id, actor["id"], "不能停用当前登录账号")
    ensure_permission_admin_remains(user_id, target_status=UserStatus.DISABLED)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.DISABLED, user_id))
    audit("disable_user", "user", user_id, actor["id"])
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def enable_user(user_id: int, actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.ACTIVE, user_id))
    audit("enable_user", "user", user_id, actor["id"])
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def delete_user(user_id: int, actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    ensure_not_current_user(user_id, actor["id"], "不能删除当前登录账号")
    ensure_permission_admin_remains(user_id, target_status=UserStatus.DELETED)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.DELETED, user_id))
    audit("delete_user", "user", user_id, actor["id"])
    return serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def get_system_settings() -> dict[str, Any]:
    rows = query_all("SELECT * FROM system_settings ORDER BY key")
    return {row["key"]: from_json(row["value_json"]) for row in rows}


def save_system_setting(key: str, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    execute(
        """
        INSERT INTO system_settings(key, value_json, saved_by, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, saved_by = excluded.saved_by, updated_at = CURRENT_TIMESTAMP
        """,
        (key, to_json(payload.get("value")), actor["id"]),
    )
    audit("save_system_setting", "system_setting", None, actor["id"], {"key": key})
    return {"key": key, "value": payload.get("value")}


def list_audit_logs(actor: dict[str, Any]) -> dict[str, Any]:
    require_permissions(actor, {Permission.SUPER_ADMIN})
    return {"items": query_all("SELECT * FROM audit_logs ORDER BY id DESC")}
