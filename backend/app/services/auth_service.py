from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def issue_checkflow_token(user: dict[str, Any]) -> dict[str, Any]:
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + timedelta(seconds=7200)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"access_token": token, "token_type": "Bearer", "expires_in": 7200, "user": serialize_user(user)}


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
    if settings.is_production or settings.auth_mode != "local":
        raise BusinessError("LOCAL_AUTH_DISABLED", "本地账号密码登录仅允许开发环境使用", 401)
    user = query_one("SELECT * FROM users WHERE uid = ?", (payload.get("uid"),))
    if not user or user["status"] != UserStatus.ACTIVE:
        raise BusinessError("INVALID_UID", "UID 不存在或已停用", 401)
    if payload.get("password") not in (user["uid"], "admin"):
        raise BusinessError("INVALID_PASSWORD", "密码无效", 401)
    return issue_checkflow_token(user)


def iam_login_url(state: str | None = None) -> dict[str, str]:
    if not settings.iam_authorize_url or not settings.iam_client_id or not settings.iam_redirect_uri:
        raise BusinessError("IAM_NOT_CONFIGURED", "IAM 登录配置不完整", 500)
    params = {
        "client_id": settings.iam_client_id,
        "response_type": "code",
        "redirect_uri": settings.iam_redirect_uri,
    }
    if state:
        params["state"] = state
    return {"login_url": f"{settings.iam_authorize_url}?{urlencode(params)}"}


def exchange_iam_code_for_token(code: str) -> dict[str, Any]:
    if not settings.iam_token_url or not settings.iam_client_id or not settings.iam_client_secret or not settings.iam_redirect_uri:
        raise RuntimeError("IAM token configuration is incomplete.")
    params = {
        "grant_type": "authorization_code",
        "client_id": settings.iam_client_id,
        "client_secret": settings.iam_client_secret,
        "code": code,
        "redirect_uri": settings.iam_redirect_uri,
        "oauth_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    request = Request(f"{settings.iam_token_url}?{urlencode(params)}", method="POST")
    with urlopen(request, timeout=10) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def fetch_iam_profile(access_token: str) -> dict[str, Any]:
    if not settings.iam_profile_url:
        raise RuntimeError("IAM profile configuration is incomplete.")
    request = Request(f"{settings.iam_profile_url}?{urlencode({'access_token': access_token})}", method="GET")
    with urlopen(request, timeout=10) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def uid_from_iam_profile(profile: dict[str, Any]) -> str | None:
    attributes = profile.get("attributes") or {}
    return attributes.get("account_no") or attributes.get("user_uid") or profile.get("id")


def iam_callback(code: str | None, _: str | None = None) -> dict[str, Any]:
    if not code:
        raise BusinessError("IAM_CODE_REQUIRED", "缺少 IAM 授权码")
    try:
        token_payload = exchange_iam_code_for_token(code)
    except Exception as exc:
        raise BusinessError("IAM_TOKEN_EXCHANGE_FAILED", "IAM token 换取失败", 401) from exc
    access_token = token_payload.get("access_token")
    if not access_token:
        raise BusinessError("IAM_TOKEN_EXCHANGE_FAILED", "IAM token 换取失败", 401)
    try:
        profile = fetch_iam_profile(access_token)
    except Exception as exc:
        raise BusinessError("IAM_PROFILE_FAILED", "IAM 用户信息获取失败", 401) from exc
    uid = uid_from_iam_profile(profile)
    if not uid:
        raise BusinessError("IAM_PROFILE_UID_MISSING", "IAM 用户信息缺少可映射 UID", 401)
    user = query_one("SELECT * FROM users WHERE uid = ? AND status = ?", (uid, UserStatus.ACTIVE))
    if not user:
        raise BusinessError("INVALID_UID", "UID 不存在或已停用", 401)
    return issue_checkflow_token(user)


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
