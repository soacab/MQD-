from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Body, Depends, FastAPI, Header

from app.core.config import settings
from app.core.cors import configure_cors
from app.core.database import create_schema, execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import (
    AdapterType,
    AutoCheckStatus,
    InspectionItemStatus,
    InspectionResult,
    InspectionRoundStatus,
    InspectionTaskStatus,
    Permission,
    ProjectStatus,
    ReportOverallResult,
    RuleItemType,
    RuleVersionStatus,
    UserStatus,
)
from app.core.exceptions import BusinessError, business_error_handler
from app.seed import seed_database
from app.vdrive import validate_vdrive_folder_link


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    seed_database()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
configure_cors(app)
app.add_exception_handler(BusinessError, business_error_handler)


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "data": data if data is not None else {}, "message": message}


def audit(action: str, entity_type: str, entity_id: int | None, actor_id: int | None, detail: dict | None = None) -> None:
    execute(
        "INSERT INTO audit_logs(actor_user_id, action, entity_type, entity_id, detail_json) VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, entity_type, entity_id, to_json(detail or {})),
    )


def row_or_404(sql: str, params: tuple[Any, ...], code: str, message: str) -> dict[str, Any]:
    row = query_one(sql, params)
    if not row:
        raise BusinessError(code, message, 404)
    return row


def permissions_for_user(user_id: int) -> list[str]:
    rows = query_all(
        "SELECT permission_code FROM user_permissions WHERE user_id = ? ORDER BY permission_code",
        (user_id,),
    )
    return [row["permission_code"] for row in rows]


def normalize_permissions(raw_permissions: list[str] | None) -> list[str]:
    permissions = []
    valid_permissions = {permission.value for permission in Permission}
    for permission in raw_permissions or []:
        if permission not in valid_permissions:
            raise BusinessError("INVALID_PERMISSION", f"未知权限 {permission}")
        if permission not in permissions:
            permissions.append(permission)
    return permissions


def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "uid": user["uid"],
        "name": user["name"],
        "email": user["email"],
        "status": user["status"],
        "permissions": permissions_for_user(user["id"]),
    }


def current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise BusinessError("UNAUTHORIZED", "缺少认证信息", 401)
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer "),
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise BusinessError("UNAUTHORIZED", "认证信息无效", 401) from exc
    user = query_one("SELECT * FROM users WHERE id = ? AND status = ?", (user_id, UserStatus.ACTIVE))
    if not user:
        raise BusinessError("UNAUTHORIZED", "用户不存在或已停用", 401)
    return user


def require_permissions(user: dict[str, Any], allowed: set[str]) -> None:
    user_permissions = set(permissions_for_user(user["id"]))
    if not user_permissions.intersection(allowed):
        raise BusinessError("FORBIDDEN", "权限不足", 403)


def business_permissions(user: dict[str, Any]) -> set[str]:
    return set(permissions_for_user(user["id"])).intersection(
        {Permission.INSPECTION_ENGINEER, Permission.PROJECT_ADMIN}
    )


def has_full_business_scope(user: dict[str, Any]) -> bool:
    return Permission.PROJECT_ADMIN in business_permissions(user)


def require_business_scope(user: dict[str, Any]) -> None:
    if not business_permissions(user):
        raise BusinessError("FORBIDDEN", "权限不足", 403)


def ensure_project_active(project: dict[str, Any]) -> None:
    if project["status"] == ProjectStatus.DELETED:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能进入业务页面")


def require_rule_read_permissions(user: dict[str, Any]) -> None:
    require_permissions(user, {Permission.RULES_ADMIN, Permission.INSPECTION_ENGINEER, Permission.PROJECT_ADMIN})


def task_in_business_scope(task: dict[str, Any], user: dict[str, Any]) -> bool:
    if has_full_business_scope(user):
        return True
    return Permission.INSPECTION_ENGINEER in business_permissions(user) and task["created_by"] == user["id"]


def project_in_business_scope(project_id: int, user: dict[str, Any]) -> bool:
    if has_full_business_scope(user):
        return True
    if Permission.INSPECTION_ENGINEER not in business_permissions(user):
        return False
    return bool(
        query_one(
            "SELECT id FROM inspection_tasks WHERE project_id = ? AND created_by = ? LIMIT 1",
            (project_id, user["id"]),
        )
    )


def require_project_scope(user: dict[str, Any], project: dict[str, Any]) -> None:
    if not project_in_business_scope(project["id"], user):
        raise BusinessError("FORBIDDEN", "权限不足", 403)
    ensure_project_active(project)


def task_project_is_active(task: dict[str, Any]) -> bool:
    project = query_one("SELECT * FROM projects WHERE id = ?", (task["project_id"],))
    return bool(project and project["status"] != ProjectStatus.DELETED)


def require_task_scope(user: dict[str, Any], task_id: int) -> dict[str, Any]:
    task = row_or_404("SELECT * FROM inspection_tasks WHERE id = ?", (task_id,), "TASK_NOT_FOUND", "点检任务不存在")
    if not task_in_business_scope(task, user):
        raise BusinessError("FORBIDDEN", "权限不足", 403)
    project = query_one("SELECT * FROM projects WHERE id = ?", (task["project_id"],))
    ensure_project_active(project)
    return task


def require_item_scope(user: dict[str, Any], item_id: int) -> dict[str, Any]:
    item = row_or_404("SELECT * FROM inspection_items WHERE id = ?", (item_id,), "ITEM_NOT_FOUND", "检查项不存在")
    require_task_scope(user, item["inspection_task_id"])
    return item


def require_rectification_scope(user: dict[str, Any], rectification_id: int) -> dict[str, Any]:
    rectification = row_or_404(
        "SELECT * FROM rectification_items WHERE id = ?",
        (rectification_id,),
        "RECTIFICATION_NOT_FOUND",
        "整改项不存在",
    )
    require_task_scope(user, rectification["inspection_task_id"])
    return rectification


def require_followup_scope(user: dict[str, Any], followup_id: int) -> dict[str, Any]:
    followup = row_or_404(
        "SELECT * FROM followup_items WHERE id = ?",
        (followup_id,),
        "FOLLOWUP_NOT_FOUND",
        "待跟进项不存在",
    )
    require_task_scope(user, followup["inspection_task_id"])
    return followup


def require_report_scope(user: dict[str, Any], report_id: int) -> dict[str, Any]:
    report = row_or_404("SELECT * FROM inspection_reports WHERE id = ?", (report_id,), "REPORT_NOT_FOUND", "报告不存在")
    require_task_scope(user, report["inspection_task_id"])
    return report


def filter_task_scoped_rows(rows: list[dict[str, Any]], user: dict[str, Any], task_key: str = "inspection_task_id") -> list[dict[str, Any]]:
    require_business_scope(user)
    filtered = []
    for row in rows:
        task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (row[task_key],))
        if not task or not task_project_is_active(task):
            continue
        if has_full_business_scope(user) or task_in_business_scope(task, user):
            filtered.append(row)
    return filtered


def require_editable_user(user_id: int) -> dict[str, Any]:
    return row_or_404(
        "SELECT * FROM users WHERE id = ? AND status != ?",
        (user_id, UserStatus.DELETED),
        "USER_NOT_FOUND",
        "用户不存在",
    )


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


def parse_vdrive_url(url: str) -> dict[str, Any]:
    return validate_vdrive_folder_link(url)


def paginate(items: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {"items": items[start : start + page_size], "page": page, "page_size": page_size, "total": len(items)}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login(payload: dict = Body(...)) -> dict[str, Any]:
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
    return ok({"access_token": token, "token_type": "Bearer", "expires_in": 7200, "user": serialize_user(user)})


@app.get("/api/v1/auth/me")
def me(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(serialize_user(user))


@app.get("/api/v1/users")
def list_users(
    keyword: str | None = None,
    status: str | None = None,
    permission: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    rows = query_all("SELECT * FROM users ORDER BY id")
    if status:
        if status not in {status.value for status in UserStatus}:
            raise BusinessError("INVALID_USER_STATUS", f"未知用户状态 {status}")
    rows = [r for r in rows if r["status"] != UserStatus.DELETED]
    if keyword:
        rows = [r for r in rows if keyword in r["uid"] or keyword in r["name"] or keyword in (r["email"] or "")]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if permission:
        if permission not in {item.value for item in Permission}:
            raise BusinessError("INVALID_PERMISSION", f"未知权限 {permission}")
        rows = [r for r in rows if permission in permissions_for_user(r["id"])]
    return ok(paginate([serialize_user(row) for row in rows], page, page_size))


@app.post("/api/v1/users")
def create_user(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
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
    audit("create_user", "user", user_id, user["id"], payload)
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.put("/api/v1/users/{user_id}")
def update_user(user_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    status = payload.get("status", UserStatus.ACTIVE)
    if status not in {UserStatus.ACTIVE, UserStatus.DISABLED}:
        raise BusinessError("INVALID_USER_STATUS", "账号状态只能为启用或停用")
    permissions = normalize_permissions(payload.get("permissions", []))
    if user_id == user["id"] and Permission.SUPER_ADMIN not in permissions:
        raise BusinessError("CURRENT_PERMISSION_ADMIN_PROTECTED", "不能取消自己的权限管理权限")
    if user_id == user["id"] and status != UserStatus.ACTIVE:
        raise BusinessError("CURRENT_USER_PROTECTED", "不能停用当前登录账号")
    ensure_permission_admin_remains(user_id, status, permissions)
    with transaction():
        execute(
            "UPDATE users SET name = ?, email = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload["name"], payload.get("email"), status, user_id),
        )
        replace_user_permissions(user_id, permissions)
        audit("update_user", "user", user_id, user["id"], payload)
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.put("/api/v1/users/{user_id}/permissions")
def update_user_permissions(user_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    permissions = normalize_permissions(payload.get("permissions", []))
    if user_id == user["id"] and Permission.SUPER_ADMIN not in permissions:
        raise BusinessError("CURRENT_PERMISSION_ADMIN_PROTECTED", "不能取消自己的权限管理权限")
    ensure_permission_admin_remains(user_id, target_permissions=permissions)
    replace_user_permissions(user_id, permissions)
    audit("update_user_permissions", "user", user_id, user["id"], payload)
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.post("/api/v1/users/{user_id}/disable")
def disable_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    ensure_not_current_user(user_id, user["id"], "不能停用当前登录账号")
    ensure_permission_admin_remains(user_id, target_status=UserStatus.DISABLED)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.DISABLED, user_id))
    audit("disable_user", "user", user_id, user["id"])
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.post("/api/v1/users/{user_id}/enable")
def enable_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.ACTIVE, user_id))
    audit("enable_user", "user", user_id, user["id"])
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.delete("/api/v1/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    require_editable_user(user_id)
    ensure_not_current_user(user_id, user["id"], "不能删除当前登录账号")
    ensure_permission_admin_remains(user_id, target_status=UserStatus.DELETED)
    execute("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (UserStatus.DELETED, user_id))
    audit("delete_user", "user", user_id, user["id"])
    return ok(serialize_user(query_one("SELECT * FROM users WHERE id = ?", (user_id,))))


@app.get("/api/v1/system-settings")
def get_system_settings(_: dict = Depends(current_user)) -> dict[str, Any]:
    rows = query_all("SELECT * FROM system_settings ORDER BY key")
    return ok({row["key"]: from_json(row["value_json"]) for row in rows})


@app.put("/api/v1/system-settings/{key}")
def save_system_setting(key: str, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    execute(
        """
        INSERT INTO system_settings(key, value_json, saved_by, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, saved_by = excluded.saved_by, updated_at = CURRENT_TIMESTAMP
        """,
        (key, to_json(payload.get("value")), user["id"]),
    )
    audit("save_system_setting", "system_setting", None, user["id"], {"key": key})
    return ok({"key": key, "value": payload.get("value")})


@app.post("/api/v1/vdrive/validate-folder-link")
def validate_vdrive_link(payload: dict = Body(...), _: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(parse_vdrive_url(payload.get("vdrive_url", "")))


@app.get("/api/v1/projects")
def list_projects(
    keyword: str | None = None,
    qg_node_id: int | None = None,
    status: str | None = None,
    mq_user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    require_business_scope(user)
    rows = query_all("SELECT * FROM projects ORDER BY id DESC")
    selected_status = status or ProjectStatus.NORMAL
    if selected_status == ProjectStatus.DELETED and not has_full_business_scope(user):
        raise BusinessError("FORBIDDEN", "deleted 项目仅项目管理员可查询", 403)
    if not has_full_business_scope(user):
        rows = [row for row in rows if project_in_business_scope(row["id"], user)]
    rows = [row for row in rows if row["status"] == selected_status]
    if qg_node_id:
        project_ids = {
            row["project_id"]
            for row in query_all("SELECT DISTINCT project_id FROM inspection_tasks WHERE qg_node_id = ?", (qg_node_id,))
        }
        rows = [row for row in rows if row["id"] in project_ids]
    if mq_user_id:
        rows = [row for row in rows if row["mq_user_id"] == mq_user_id]
    if keyword:
        rows = [row for row in rows if project_matches_keyword(row, keyword)]
    return ok(paginate([project_detail(row) for row in rows], page, page_size))


def project_matches_keyword(project: dict[str, Any], keyword: str) -> bool:
    if keyword in project["project_name"] or keyword in project["customer"]:
        return True
    return bool(
        query_one(
            "SELECT id FROM project_models WHERE project_id = ? AND model_name LIKE ? LIMIT 1",
            (project["id"], f"%{keyword}%"),
        )
    )


def project_detail(project: dict[str, Any]) -> dict[str, Any]:
    orders = query_all("SELECT * FROM project_orders WHERE project_id = ? ORDER BY id", (project["id"],))
    models = query_all("SELECT * FROM project_models WHERE project_id = ? ORDER BY id", (project["id"],))
    return {
        **project,
        "vdrive": {
            "url": project["vdrive_url"],
            "folder_guid": project["vdrive_folder_guid"],
            "folder_id": project["vdrive_folder_id"],
            "folder_name": project["vdrive_folder_name"],
            "folder_path": project["vdrive_folder_path"],
        },
        "orders": orders,
        "models": models,
    }


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_business_scope(user)
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    require_project_scope(user, project)
    return ok(project_detail(project))


@app.post("/api/v1/projects")
def create_project(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    for field in ("project_name", "customer", "receive_date"):
        if not payload.get(field):
            raise BusinessError("PROJECT_REQUIRED_FIELD", f"缺少必填字段 {field}")
    vdrive = parse_vdrive_url(payload.get("vdrive_url", ""))
    mq_user = query_one("SELECT name FROM users WHERE id = ?", (payload.get("mq_user_id"),))
    with transaction():
        cur = execute(
            """
            INSERT INTO projects(
                project_name, customer, project_category, bu, project_level, mq_user_id,
                mq_user_name_snapshot, mp_owner, group_name, planned_mp_date, production_line,
                vdrive_url, vdrive_folder_guid, vdrive_folder_id, vdrive_folder_name, vdrive_folder_path,
                created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["project_name"],
                payload["customer"],
                payload.get("project_category"),
                payload.get("bu"),
                payload.get("project_level"),
                payload.get("mq_user_id"),
                mq_user["name"] if mq_user else None,
                payload.get("mp_owner"),
                payload.get("group_name"),
                payload.get("planned_mp_date"),
                payload.get("production_line"),
                payload.get("vdrive_url"),
                vdrive["folder_guid"],
                vdrive["folder_id"],
                vdrive["folder_name"],
                vdrive["folder_path"],
                user["id"],
            ),
        )
        project_id = cur.lastrowid
        add_project_order_rows(project_id, payload["receive_date"], payload.get("models", []), user["id"])
        audit("create_project", "project", project_id, user["id"], payload)
    return ok(project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,))))


def add_project_order_rows(project_id: int, receive_date: str, models: list[str], created_by: int) -> int:
    cur = execute(
        "INSERT INTO project_orders(project_id, receive_date, created_by) VALUES (?, ?, ?)",
        (project_id, receive_date, created_by),
    )
    order_id = cur.lastrowid
    for model in models:
        execute(
            "INSERT INTO project_models(project_id, project_order_id, model_name) VALUES (?, ?, ?)",
            (project_id, order_id, model),
        )
    return order_id


@app.patch("/api/v1/projects/{project_id}")
def update_project(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] == ProjectStatus.DELETED:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能编辑")
    fields = ["project_name", "customer", "project_category", "bu", "project_level", "mq_user_id", "mp_owner", "group_name", "planned_mp_date", "production_line"]
    for field in fields:
        if field in payload:
            execute(f"UPDATE projects SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload[field], project_id))
    audit("update_project", "project", project_id, user["id"], payload)
    return ok(project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,))))


@app.post("/api/v1/projects/{project_id}/vdrive-link")
def update_project_vdrive(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能修改 VDrive")
    vdrive = parse_vdrive_url(payload.get("vdrive_url", ""))
    execute(
        """
        UPDATE projects SET vdrive_url = ?, vdrive_folder_guid = ?, vdrive_folder_id = ?,
        vdrive_folder_name = ?, vdrive_folder_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """,
        (payload["vdrive_url"], vdrive["folder_guid"], vdrive["folder_id"], vdrive["folder_name"], vdrive["folder_path"], project_id),
    )
    audit("update_project_vdrive", "project", project_id, user["id"], payload)
    return ok(project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,))))


@app.post("/api/v1/projects/{project_id}/orders")
def add_project_order(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能加单")
    active_task = query_one(
        "SELECT id FROM inspection_tasks WHERE project_id = ? AND status IN (?, ?) LIMIT 1",
        (project_id, InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING),
    )
    if active_task:
        raise BusinessError("PROJECT_HAS_ACTIVE_TASK", "项目存在进行中或整改中任务，不能加单")
    order_id = add_project_order_rows(project_id, payload["receive_date"], payload.get("models", []), user["id"])
    audit("add_project_order", "project", project_id, user["id"], payload)
    return ok({"id": order_id})


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if payload.get("confirm_project_name") != project["project_name"]:
        raise BusinessError("PROJECT_CONFIRM_NAME_MISMATCH", "项目名称确认不匹配")
    execute(
        """
        UPDATE projects SET status = ?, deleted_by = ?, deleted_at = CURRENT_TIMESTAMP,
        delete_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """,
        (ProjectStatus.DELETED, user["id"], payload.get("delete_reason"), project_id),
    )
    audit("delete_project", "project", project_id, user["id"], payload)
    return ok(project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,))))


@app.get("/api/v1/qg-nodes")
def list_qg_nodes(user: dict = Depends(current_user)) -> dict[str, Any]:
    require_rule_read_permissions(user)
    return ok({"items": query_all("SELECT * FROM qg_nodes WHERE is_active = 1 ORDER BY sort_order")})


def serialize_rule_version(version: dict[str, Any]) -> dict[str, Any]:
    publisher = query_one("SELECT name FROM users WHERE id = ?", (version.get("published_by"),))
    current = query_one(
        """
        SELECT id FROM business_rule_versions
        WHERE qg_node_id = ? AND status = ?
        ORDER BY published_at DESC, id DESC LIMIT 1
        """,
        (version["qg_node_id"], RuleVersionStatus.PUBLISHED),
    )
    return {
        **version,
        "published_by_name": publisher["name"] if publisher else None,
        "is_current": bool(
            version["status"] == RuleVersionStatus.PUBLISHED
            and current
            and current["id"] == version["id"]
        ),
        "change_details": rule_version_change_details(version["id"]),
    }


def rule_version_change_details(version_id: int) -> list[dict[str, Any]]:
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order, id", (version_id,))
    details = []
    for rule in rules:
        details.append(
            {
                "rule_code": rule["rule_code"],
                "item_name": rule["item_name"],
                "change_type": "disabled" if not rule["is_active"] else "added",
                "change_summary": "停用检查项" if not rule["is_active"] else "新增或保留检查项",
            }
        )
    return details


@app.get("/api/v1/business-rule-versions")
def list_rule_versions(qg_node_id: int | None = None, status: str | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_rule_read_permissions(user)
    rows = query_all("SELECT * FROM business_rule_versions ORDER BY id DESC")
    if qg_node_id:
        rows = [row for row in rows if row["qg_node_id"] == qg_node_id]
    if status:
        rows = [row for row in rows if row["status"] == status]
    return ok({"items": [serialize_rule_version(row) for row in rows]})


@app.post("/api/v1/business-rule-versions")
def create_rule_version(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    cur = execute(
        "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
        (payload["qg_node_id"], payload["version_no"], payload.get("change_summary"), user["id"]),
    )
    audit("create_rule_version", "business_rule_version", cur.lastrowid, user["id"], payload)
    return ok(serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (cur.lastrowid,))))


@app.get("/api/v1/business-rule-versions/{version_id}")
def get_rule_version(version_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_rule_read_permissions(user)
    version = row_or_404("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,), "RULE_VERSION_NOT_FOUND", "规则版本不存在")
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order", (version_id,))
    for rule in rules:
        rule["auto_check_execution_rules"] = query_all(
            "SELECT * FROM auto_check_execution_rules WHERE business_check_rule_id = ? ORDER BY id",
            (rule["id"],),
        )
    detail = serialize_rule_version(version)
    detail["business_check_rules"] = rules
    return ok(detail)


@app.post("/api/v1/business-rule-versions/{version_id}/business-check-rules")
def create_business_rule(version_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    version = row_or_404("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,), "RULE_VERSION_NOT_FOUND", "规则版本不存在")
    if version["status"] != RuleVersionStatus.DRAFT:
        raise BusinessError("RULE_VERSION_NOT_DRAFT", "只有草稿规则版本可编辑")
    cur = execute(
        """
        INSERT INTO business_check_rules(
            business_rule_version_id, qg_node_id, rule_code, item_name, item_type,
            check_type, checklist_requirement, owner_dept, is_apqp, is_active, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            version["qg_node_id"],
            payload["rule_code"],
            payload["item_name"],
            payload["item_type"],
            payload["check_type"],
            payload.get("checklist_requirement"),
            payload.get("owner_dept"),
            1 if payload.get("is_apqp") else 0,
            1 if payload.get("is_active", True) else 0,
            payload.get("sort_order", 0),
        ),
    )
    audit("create_business_rule", "business_check_rule", cur.lastrowid, user["id"], payload)
    return ok(query_one("SELECT * FROM business_check_rules WHERE id = ?", (cur.lastrowid,)))


@app.patch("/api/v1/business-check-rules/{rule_id}")
def update_business_rule(rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_rule(rule_id)
    for field in ("item_name", "item_type", "check_type", "checklist_requirement", "owner_dept", "sort_order"):
        if field in payload:
            execute(f"UPDATE business_check_rules SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload[field], rule_id))
    if "is_apqp" in payload:
        execute("UPDATE business_check_rules SET is_apqp = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if payload["is_apqp"] else 0, rule_id))
    if "is_active" in payload:
        execute("UPDATE business_check_rules SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if payload["is_active"] else 0, rule_id))
    audit("update_business_rule", "business_check_rule", rule_id, user["id"], payload)
    return ok(query_one("SELECT * FROM business_check_rules WHERE id = ?", (rule_id,)))


@app.post("/api/v1/business-check-rules/{rule_id}/auto-check-execution-rules")
def create_execution_rule(rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_rule(rule_id)
    cur = execute(
        """
        INSERT INTO auto_check_execution_rules(
            business_check_rule_id, execution_code, execution_mode, adapter_type,
            config_json, config_version, is_enabled, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rule_id,
            payload["execution_code"],
            payload["execution_mode"],
            payload["adapter_type"],
            to_json(payload.get("config_json", {})),
            payload["config_version"],
            1 if payload.get("is_enabled", True) else 0,
            user["id"],
        ),
    )
    audit("create_execution_rule", "auto_check_execution_rule", cur.lastrowid, user["id"], payload)
    return ok(query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (cur.lastrowid,)))


@app.patch("/api/v1/auto-check-execution-rules/{execution_rule_id}")
def update_execution_rule(execution_rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    for field in ("execution_code", "execution_mode", "adapter_type", "config_version"):
        if field in payload:
            execute(f"UPDATE auto_check_execution_rules SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload[field], execution_rule_id))
    if "config_json" in payload:
        execute("UPDATE auto_check_execution_rules SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (to_json(payload["config_json"]), execution_rule_id))
    if "is_enabled" in payload:
        execute("UPDATE auto_check_execution_rules SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if payload["is_enabled"] else 0, execution_rule_id))
    return ok(query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,)))


@app.post("/api/v1/auto-check-execution-rules/{execution_rule_id}/enable")
def enable_execution_rule(execution_rule_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    execute("UPDATE auto_check_execution_rules SET is_enabled = 1 WHERE id = ?", (execution_rule_id,))
    return ok(query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,)))


@app.post("/api/v1/auto-check-execution-rules/{execution_rule_id}/disable")
def disable_execution_rule(execution_rule_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    execute("UPDATE auto_check_execution_rules SET is_enabled = 0 WHERE id = ?", (execution_rule_id,))
    return ok(query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,)))


@app.post("/api/v1/business-rule-versions/{version_id}/publish")
def publish_rule_version(version_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    version = row_or_404("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,), "RULE_VERSION_NOT_FOUND", "规则版本不存在")
    if version["status"] != RuleVersionStatus.DRAFT:
        raise BusinessError("RULE_VERSION_NOT_DRAFT", "只有草稿版本可发布")
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? AND is_active = 1", (version_id,))
    for rule in rules:
        if rule["item_type"] in (RuleItemType.AUTO, RuleItemType.SYSTEM):
            execution = query_one(
                "SELECT id FROM auto_check_execution_rules WHERE business_check_rule_id = ? AND is_enabled = 1",
                (rule["id"],),
            )
            if not execution:
                raise BusinessError("AUTO_RULE_MISSING_EXECUTION", "自动检查项缺少启用的执行规则")
    with transaction():
        execute(
            "UPDATE business_rule_versions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE qg_node_id = ? AND status = ?",
            (RuleVersionStatus.DEPRECATED, version["qg_node_id"], RuleVersionStatus.PUBLISHED),
        )
        execute(
            "UPDATE business_rule_versions SET status = ?, published_by = ?, published_at = CURRENT_TIMESTAMP WHERE id = ?",
            (RuleVersionStatus.PUBLISHED, user["id"], version_id),
        )
        audit("publish_rule_version", "business_rule_version", version_id, user["id"])
    return ok(serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,))))


def ensure_rule_version_draft_for_rule(rule_id: int) -> dict[str, Any]:
    rule = row_or_404("SELECT * FROM business_check_rules WHERE id = ?", (rule_id,), "BUSINESS_RULE_NOT_FOUND", "业务规则不存在")
    version = query_one("SELECT * FROM business_rule_versions WHERE id = ?", (rule["business_rule_version_id"],))
    if version["status"] != RuleVersionStatus.DRAFT:
        raise BusinessError("RULE_VERSION_NOT_DRAFT", "已发布或已废弃规则版本不可编辑")
    return rule


def ensure_rule_version_draft_for_execution_rule(execution_rule_id: int) -> dict[str, Any]:
    execution = row_or_404(
        "SELECT * FROM auto_check_execution_rules WHERE id = ?",
        (execution_rule_id,),
        "EXECUTION_RULE_NOT_FOUND",
        "执行规则不存在",
    )
    ensure_rule_version_draft_for_rule(execution["business_check_rule_id"])
    return execution


@app.post("/api/v1/business-rule-versions/{version_id}/deprecate")
def deprecate_rule_version(version_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    execute("UPDATE business_rule_versions SET status = ? WHERE id = ?", (RuleVersionStatus.DEPRECATED, version_id))
    audit("deprecate_rule_version", "business_rule_version", version_id, user["id"])
    return ok(serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,))))


def build_rule_snapshots(version_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? AND is_active = 1 ORDER BY sort_order", (version_id,))
    business_snapshot: list[dict[str, Any]] = []
    execution_snapshot: list[dict[str, Any]] = []
    for rule in rules:
        business_snapshot.append(rule)
        executions = query_all(
            "SELECT * FROM auto_check_execution_rules WHERE business_check_rule_id = ? AND is_enabled = 1 ORDER BY id",
            (rule["id"],),
        )
        for execution in executions:
            execution["config_json"] = from_json(execution["config_json"], {})
            execution_snapshot.append(execution)
    return business_snapshot, execution_snapshot


@app.post("/api/v1/inspection-tasks")
def create_inspection_task(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (payload["project_id"],), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能创建点检任务")
    if not project["vdrive_folder_guid"] or not project["vdrive_folder_id"]:
        raise BusinessError("PROJECT_VDRIVE_REQUIRED", "项目缺少 VDrive 文件夹标识")
    version = query_one(
        "SELECT * FROM business_rule_versions WHERE qg_node_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
        (payload["qg_node_id"], RuleVersionStatus.PUBLISHED),
    )
    if not version:
        raise BusinessError("PUBLISHED_RULE_VERSION_REQUIRED", "当前 QG 节点没有已发布规则版本")
    active = query_one(
        "SELECT * FROM inspection_tasks WHERE project_id = ? AND qg_node_id = ? AND status IN (?, ?)",
        (payload["project_id"], payload["qg_node_id"], InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING),
    )
    if active:
        raise BusinessError("ACTIVE_TASK_EXISTS", "同项目同节点已有进行中或整改中任务")

    task_no = f"IT-{payload['project_id']}-{payload['qg_node_id']}-{version['id']}"
    with transaction():
        cur = execute(
            """
            INSERT INTO inspection_tasks(project_id, qg_node_id, task_no, status, current_round_no, created_by)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (payload["project_id"], payload["qg_node_id"], task_no, InspectionTaskStatus.RUNNING, user["id"]),
        )
        task_id = cur.lastrowid
        business_snapshot, execution_snapshot = build_rule_snapshots(version["id"])
        snapshot_cur = execute(
            """
            INSERT INTO rule_snapshots(
                inspection_task_id, business_rule_version_id, business_rule_snapshot_json,
                auto_check_execution_rule_snapshot_json
            ) VALUES (?, ?, ?, ?)
            """,
            (task_id, version["id"], to_json(business_snapshot), to_json(execution_snapshot)),
        )
        round_cur = execute(
            "INSERT INTO inspection_rounds(inspection_task_id, round_no, status) VALUES (?, 1, ?)",
            (task_id, InspectionRoundStatus.RUNNING),
        )
        round_id = round_cur.lastrowid
        generate_items_for_round(task_id, round_id, business_snapshot, execution_snapshot)
        report_cur = execute(
            """
            INSERT INTO inspection_reports(
                inspection_task_id, project_id, qg_node_id, report_no,
                latest_round_no, business_rule_version_no, generated_by
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (task_id, project["id"], payload["qg_node_id"], f"REP-{task_id}", version["version_no"], user["id"]),
        )
        audit("create_inspection_task", "inspection_task", task_id, user["id"], payload)
    return ok(
        {
            "inspection_task_id": task_id,
            "project_id": project["id"],
            "qg_node_id": payload["qg_node_id"],
            "status": InspectionTaskStatus.RUNNING.value,
            "current_round_no": 1,
            "round_id": round_id,
            "rule_snapshot_id": snapshot_cur.lastrowid,
            "report_id": report_cur.lastrowid,
        }
    )


def generate_items_for_round(task_id: int, round_id: int, business_snapshot: list[dict[str, Any]], execution_snapshot: list[dict[str, Any]], only_rule_codes: set[str] | None = None) -> None:
    execution_rules_by_business_rule_id = {row["business_check_rule_id"]: row for row in execution_snapshot}
    for rule in business_snapshot:
        if only_rule_codes is not None and rule["rule_code"] not in only_rule_codes:
            continue
        if rule["item_type"] == RuleItemType.INHERIT:
            status = InspectionItemStatus.INHERITED
            final_result = InspectionResult.INHERIT
        elif rule["item_type"] in (RuleItemType.AUTO, RuleItemType.SYSTEM) and rule["id"] in execution_rules_by_business_rule_id:
            status = InspectionItemStatus.PENDING
            final_result = None
        else:
            status = InspectionItemStatus.MANUAL_REQUIRED
            final_result = None
        cur = execute(
            """
            INSERT INTO inspection_items(
                inspection_task_id, inspection_round_id, source_rule_code, source_business_rule_id,
                item_name_snapshot, item_type_snapshot, check_type_snapshot, checklist_requirement_snapshot,
                owner_dept_snapshot, is_apqp_snapshot, sort_order, status, final_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                round_id,
                rule["rule_code"],
                rule["id"],
                rule["item_name"],
                rule["item_type"],
                rule["check_type"],
                rule.get("checklist_requirement"),
                rule.get("owner_dept"),
                rule.get("is_apqp", 0),
                rule.get("sort_order", 0),
                status,
                final_result,
            ),
        )
        if status == InspectionItemStatus.PENDING:
            run_mock_auto_check(cur.lastrowid, execution_rules_by_business_rule_id[rule["id"]])


def run_mock_auto_check(item_id: int, execution_rule_snapshot: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO auto_check_results(
            inspection_item_id, attempt_no, is_latest, auto_status, auto_result,
            confidence, evidence_text, source_system, execution_rule_snapshot,
            raw_result_json, started_at, finished_at
        ) VALUES (?, 1, 1, ?, ?, 0.9, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            item_id,
            AutoCheckStatus.SUCCESS,
            InspectionResult.PASS,
            "Mock adapter found matching evidence; engineer confirmation is still required.",
            execution_rule_snapshot.get("adapter_type", AdapterType.MOCK),
            to_json(execution_rule_snapshot),
            to_json({"mock": True}),
        ),
    )
    execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.AUTO_COMPLETED, item_id))


@app.get("/api/v1/inspection-tasks")
def list_inspection_tasks(status: str | None = None, project_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_business_scope(user)
    rows = query_all("SELECT * FROM inspection_tasks ORDER BY id DESC")
    rows = [row for row in rows if task_project_is_active(row)]
    if not has_full_business_scope(user):
        rows = [row for row in rows if task_in_business_scope(row, user)]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if project_id:
        rows = [row for row in rows if row["project_id"] == project_id]
    return ok({"items": rows})


@app.get("/api/v1/inspection-tasks/{task_id}")
def get_inspection_task(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    task = require_task_scope(user, task_id)
    project = query_one("SELECT * FROM projects WHERE id = ?", (task["project_id"],))
    qg_node = query_one("SELECT * FROM qg_nodes WHERE id = ?", (task["qg_node_id"],))
    current_round = query_one(
        "SELECT * FROM inspection_rounds WHERE inspection_task_id = ? AND round_no = ?",
        (task_id, task["current_round_no"]),
    )
    items = query_all("SELECT * FROM inspection_items WHERE inspection_task_id = ?", (task_id,))
    task["project"] = project
    task["qg_node"] = qg_node
    task["current_round"] = current_round
    task["summary"] = {
        "total_items": len(items),
        "confirmed_count": len([i for i in items if i["status"] in (InspectionItemStatus.CONFIRMED, InspectionItemStatus.INHERITED)]),
        "pending_count": len([i for i in items if i["status"] not in (InspectionItemStatus.CONFIRMED, InspectionItemStatus.INHERITED)]),
    }
    return ok(task)


@app.get("/api/v1/inspection-tasks/{task_id}/current-round/items")
def current_round_items(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    task = require_task_scope(user, task_id)
    round_row = row_or_404(
        "SELECT * FROM inspection_rounds WHERE inspection_task_id = ? AND round_no = ?",
        (task_id, task["current_round_no"]),
        "ROUND_NOT_FOUND",
        "当前轮不存在",
    )
    items = query_all("SELECT * FROM inspection_items WHERE inspection_round_id = ? ORDER BY sort_order", (round_row["id"],))
    return ok({"round_id": round_row["id"], "round_no": round_row["round_no"], "items": items})


def scoped_tasks_for_dashboard(user: dict[str, Any]) -> list[dict[str, Any]]:
    require_business_scope(user)
    rows = query_all("SELECT * FROM inspection_tasks ORDER BY id DESC")
    rows = [row for row in rows if task_project_is_active(row)]
    if has_full_business_scope(user):
        return rows
    return [row for row in rows if task_in_business_scope(row, user)]


def task_progress(task_id: int) -> dict[str, int]:
    items = query_all("SELECT status FROM inspection_items WHERE inspection_task_id = ?", (task_id,))
    confirmed = len([item for item in items if item["status"] in (InspectionItemStatus.CONFIRMED, InspectionItemStatus.INHERITED)])
    return {"total": len(items), "confirmed": confirmed, "pending": len(items) - confirmed}


def dashboard_task_card(task: dict[str, Any], todo_type: str) -> dict[str, Any]:
    project = query_one("SELECT project_name FROM projects WHERE id = ?", (task["project_id"],))
    qg_node = query_one("SELECT node_code FROM qg_nodes WHERE id = ?", (task["qg_node_id"],))
    progress = task_progress(task["id"])
    return {
        "type": todo_type,
        "target_id": task["id"],
        "task_id": task["id"],
        "project_id": task["project_id"],
        "project_name": project["project_name"] if project else "",
        "qg_node": qg_node["node_code"] if qg_node else "",
        "status": task["status"],
        "href": f"/inspection?task_id={task['id']}",
        "summary": f"{progress['confirmed']}/{progress['total']} 项已确认",
    }


@app.get("/api/v1/dashboard/overview")
def dashboard_overview(user: dict = Depends(current_user)) -> dict[str, Any]:
    tasks = scoped_tasks_for_dashboard(user)
    rectifications = filter_task_scoped_rows(query_all("SELECT * FROM rectification_items ORDER BY id"), user)
    followups = filter_task_scoped_rows(query_all("SELECT * FROM followup_items ORDER BY id"), user)

    running = [task for task in tasks if task["status"] == InspectionTaskStatus.RUNNING]
    archive_ready = []
    for task in running:
        progress = task_progress(task["id"])
        if progress["total"] > 0 and progress["pending"] == 0:
            archive_ready.append(task)

    return ok(
        {
            "running_count": len(running),
            "recheck_count": len([task for task in tasks if task["status"] == InspectionTaskStatus.RECTIFYING]),
            "rectification_count": len([item for item in rectifications if not item["marked_done_at"]]),
            "followup_count": len([item for item in followups if not item["closed_at"]]),
            "archive_ready_count": len(archive_ready),
        }
    )


@app.get("/api/v1/dashboard/my-todos")
def dashboard_my_todos(user: dict = Depends(current_user)) -> dict[str, Any]:
    tasks = scoped_tasks_for_dashboard(user)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task["status"] == InspectionTaskStatus.RUNNING:
            progress = task_progress(task["id"])
            rows.append(dashboard_task_card(task, "archive_ready" if progress["total"] > 0 and progress["pending"] == 0 else "running_task"))
        elif task["status"] == InspectionTaskStatus.RECTIFYING:
            rows.append(dashboard_task_card(task, "recheck_task"))

    for item in filter_task_scoped_rows(query_all("SELECT * FROM rectification_items ORDER BY planned_finish_date, id"), user):
        if not item["marked_done_at"]:
            rows.append(
                {
                    "type": "rectification_item",
                    "target_id": item["id"],
                    "task_id": item["inspection_task_id"],
                    "project_id": item["project_id"],
                    "title": item["item_name_snapshot"],
                    "status": "pending",
                    "href": f"/rectification?task_id={item['inspection_task_id']}",
                    "summary": f"整改责任人：{item['responsible_owner']}",
                    "planned_finish_date": item["planned_finish_date"],
                }
            )

    for item in filter_task_scoped_rows(query_all("SELECT * FROM followup_items ORDER BY planned_finish_date, id"), user):
        if not item["closed_at"]:
            rows.append(
                {
                    "type": "followup_item",
                    "target_id": item["id"],
                    "task_id": item["inspection_task_id"],
                    "project_id": item["project_id"],
                    "title": item["item_name_snapshot"],
                    "status": "pending",
                    "href": f"/rectification?task_id={item['inspection_task_id']}",
                    "summary": f"待跟进责任人：{item['responsible_owner']}",
                    "planned_finish_date": item["planned_finish_date"],
                }
            )

    return ok({"items": rows, "total": len(rows)})


@app.get("/api/v1/inspection-items/{item_id}")
def get_inspection_item(item_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    item = require_item_scope(user, item_id)
    item["engineer_decisions"] = query_all("SELECT * FROM engineer_decisions WHERE inspection_item_id = ? ORDER BY id", (item_id,))
    item["auto_check_results"] = query_all("SELECT * FROM auto_check_results WHERE inspection_item_id = ? ORDER BY id", (item_id,))
    return ok(item)


@app.post("/api/v1/inspection-items/{item_id}/convert-to-manual")
def convert_to_manual(item_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    item = require_item_scope(user, item_id)
    ensure_item_mutable(item)
    execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.MANUAL_REQUIRED, item_id))
    audit("convert_to_manual", "inspection_item", item_id, user["id"], payload)
    return ok(query_one("SELECT * FROM inspection_items WHERE id = ?", (item_id,)))


@app.post("/api/v1/inspection-items/{item_id}/confirm")
def confirm_item(item_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    item = require_item_scope(user, item_id)
    ensure_item_mutable(item)
    result = payload.get("decision_result")
    if result not in (InspectionResult.PASS, InspectionResult.FAIL, InspectionResult.CONDITIONAL, InspectionResult.NA):
        raise BusinessError("INVALID_DECISION_RESULT", "结论必须是 pass、fail、conditional 或 na")
    if not payload.get("decision_text"):
        raise BusinessError("DECISION_TEXT_REQUIRED", "判断说明必填")
    if result == InspectionResult.FAIL and (not payload.get("responsible_owner") or not payload.get("planned_finish_date")):
        raise BusinessError("FAIL_FIELDS_REQUIRED", "不满足结论必须填写责任人、计划完成时间和说明")
    if result == InspectionResult.CONDITIONAL and (not payload.get("countermeasure") or not payload.get("responsible_owner") or not payload.get("planned_finish_date")):
        raise BusinessError("CONDITIONAL_FIELDS_REQUIRED", "带条件满足必须填写对策、责任人和计划完成时间")
    cur = execute(
        """
        INSERT INTO engineer_decisions(
            inspection_item_id, decision_result, decision_text, responsible_owner,
            countermeasure, planned_finish_date, override_auto_result, override_reason, decided_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            result,
            payload["decision_text"],
            payload.get("responsible_owner"),
            payload.get("countermeasure"),
            payload.get("planned_finish_date"),
            1 if payload.get("override_auto_result") else 0,
            payload.get("override_reason"),
            user["id"],
        ),
    )
    execute(
        "UPDATE inspection_items SET final_result = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (result, InspectionItemStatus.CONFIRMED, item_id),
    )
    audit("confirm_item", "inspection_item", item_id, user["id"], payload)
    return ok({"item": query_one("SELECT * FROM inspection_items WHERE id = ?", (item_id,)), "decision_id": cur.lastrowid})


def ensure_item_mutable(item: dict[str, Any]) -> None:
    task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (item["inspection_task_id"],))
    round_row = query_one("SELECT * FROM inspection_rounds WHERE id = ?", (item["inspection_round_id"],))
    if task["status"] != InspectionTaskStatus.RUNNING or round_row["status"] != InspectionRoundStatus.RUNNING:
        raise BusinessError("ITEM_NOT_MUTABLE", "当前检查项不允许修改")


@app.post("/api/v1/inspection-tasks/{task_id}/archive-current-round")
def archive_current_round(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    task = require_task_scope(user, task_id)
    if task["status"] != InspectionTaskStatus.RUNNING:
        raise BusinessError("INSPECTION_TASK_NOT_RUNNING", "当前任务不是进行中状态，无法归档")
    round_row = row_or_404(
        "SELECT * FROM inspection_rounds WHERE inspection_task_id = ? AND round_no = ?",
        (task_id, task["current_round_no"]),
        "ROUND_NOT_FOUND",
        "当前轮不存在",
    )
    if round_row["status"] != InspectionRoundStatus.RUNNING:
        raise BusinessError("ROUND_NOT_RUNNING", "当前轮不是进行中状态")
    items = query_all("SELECT * FROM inspection_items WHERE inspection_round_id = ? ORDER BY sort_order", (round_row["id"],))
    unfinished = [item for item in items if item["status"] not in (InspectionItemStatus.CONFIRMED, InspectionItemStatus.INHERITED)]
    if unfinished:
        raise BusinessError("ROUND_HAS_UNFINISHED_ITEMS", "存在未确认检查项", details={"item_ids": [i["id"] for i in unfinished]})
    results = [item["final_result"] for item in items]
    if InspectionResult.FAIL in results:
        overall_result = ReportOverallResult.NO_GO
        task_status = InspectionTaskStatus.RECTIFYING
    elif InspectionResult.CONDITIONAL in results:
        overall_result = ReportOverallResult.C_GO
        task_status = InspectionTaskStatus.COMPLETED
    else:
        overall_result = ReportOverallResult.FULL_GO
        task_status = InspectionTaskStatus.COMPLETED
    with transaction():
        execute("UPDATE inspection_rounds SET status = ?, archived_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionRoundStatus.ARCHIVED, round_row["id"]))
        execute(
            """
            UPDATE inspection_tasks SET status = ?, archived_at = CURRENT_TIMESTAMP,
            completed_at = CASE WHEN ? = ? THEN CURRENT_TIMESTAMP ELSE completed_at END,
            last_operated_at = CURRENT_TIMESTAMP WHERE id = ?
            """,
            (task_status, task_status, InspectionTaskStatus.COMPLETED, task_id),
        )
        rectification_count, followup_count = generate_work_items(task, round_row, items, user["id"])
        report = update_report(task_id, round_row, items, overall_result)
        audit("archive_current_round", "inspection_task", task_id, user["id"], {"overall_result": overall_result})
    return ok(
        {
            "inspection_task_id": task_id,
            "archived_round_no": round_row["round_no"],
            "overall_result": overall_result.value,
            "task_status": task_status.value,
            "generated_rectification_count": rectification_count,
            "generated_followup_count": followup_count,
            "report_id": report["id"],
        }
    )


def latest_decision(item_id: int) -> dict[str, Any] | None:
    return query_one("SELECT * FROM engineer_decisions WHERE inspection_item_id = ? ORDER BY id DESC LIMIT 1", (item_id,))


def generate_work_items(task: dict[str, Any], round_row: dict[str, Any], items: list[dict[str, Any]], actor_id: int) -> tuple[int, int]:
    rectification_count = 0
    followup_count = 0
    for item in items:
        decision = latest_decision(item["id"]) or {}
        if item["final_result"] == InspectionResult.FAIL and not query_one("SELECT id FROM rectification_items WHERE source_item_id = ?", (item["id"],)):
            execute(
                """
                INSERT INTO rectification_items(
                    inspection_task_id, source_round_id, source_item_id, project_id,
                    item_name_snapshot, problem_desc, responsible_owner, planned_finish_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    round_row["id"],
                    item["id"],
                    task["project_id"],
                    item["item_name_snapshot"],
                    decision.get("decision_text") or "不满足",
                    decision.get("responsible_owner") or item["owner_dept_snapshot"] or "未指定",
                    decision.get("planned_finish_date") or "2099-12-31",
                ),
            )
            rectification_count += 1
        if item["final_result"] == InspectionResult.CONDITIONAL and not query_one("SELECT id FROM followup_items WHERE source_item_id = ?", (item["id"],)):
            execute(
                """
                INSERT INTO followup_items(
                    inspection_task_id, source_round_id, source_item_id, project_id,
                    item_name_snapshot, countermeasure, responsible_owner, planned_finish_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    round_row["id"],
                    item["id"],
                    task["project_id"],
                    item["item_name_snapshot"],
                    decision.get("countermeasure") or "跟进落实",
                    decision.get("responsible_owner") or item["owner_dept_snapshot"] or "未指定",
                    decision.get("planned_finish_date") or "2099-12-31",
                ),
            )
            followup_count += 1
    return rectification_count, followup_count


def update_report(task_id: int, round_row: dict[str, Any], items: list[dict[str, Any]], overall_result: str) -> dict[str, Any]:
    report = query_one("SELECT * FROM inspection_reports WHERE inspection_task_id = ?", (task_id,))
    execute(
        """
        UPDATE inspection_reports SET overall_result = ?, latest_round_no = ?,
        last_modified_at = CURRENT_TIMESTAMP, summary_json = ? WHERE id = ?
        """,
        (
            overall_result,
            round_row["round_no"],
            to_json({"total": len(items), "fail": len([i for i in items if i["final_result"] == InspectionResult.FAIL])}),
            report["id"],
        ),
    )
    for item in items:
        decision = latest_decision(item["id"])
        process_record = {
            "round_no": round_row["round_no"],
            "inspection_item_id": item["id"],
            "final_result": item["final_result"],
            "decision_text": decision["decision_text"] if decision else None,
            "decided_by": decision["decided_by"] if decision else None,
        }
        existing = query_one("SELECT * FROM report_items WHERE report_id = ? AND source_rule_code = ?", (report["id"], item["source_rule_code"]))
        if existing:
            records = from_json(existing["process_records_json"], [])
            records.append(process_record)
            execute(
                """
                UPDATE report_items SET latest_inspection_item_id = ?, engineer_decision_snapshot = ?,
                final_result = ?, process_records_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (item["id"], to_json(decision), item["final_result"], to_json(records), existing["id"]),
            )
        else:
            execute(
                """
                INSERT INTO report_items(
                    report_id, source_rule_code, item_name_snapshot, item_type_snapshot,
                    check_type_snapshot, checklist_requirement_snapshot, latest_inspection_item_id,
                    engineer_decision_snapshot, final_result, process_records_json, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report["id"],
                    item["source_rule_code"],
                    item["item_name_snapshot"],
                    item["item_type_snapshot"],
                    item["check_type_snapshot"],
                    item["checklist_requirement_snapshot"],
                    item["id"],
                    to_json(decision),
                    item["final_result"],
                    to_json([process_record]),
                    item["sort_order"],
                ),
            )
    return query_one("SELECT * FROM inspection_reports WHERE id = ?", (report["id"],))


@app.post("/api/v1/inspection-tasks/{task_id}/void")
def void_task(task_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    task = require_task_scope(user, task_id)
    if task["status"] not in (InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING):
        raise BusinessError("TASK_CANNOT_BE_VOIDED", "当前状态不能作废")
    execute(
        "UPDATE inspection_tasks SET status = ?, voided_by = ?, voided_at = CURRENT_TIMESTAMP, void_reason = ? WHERE id = ?",
        (InspectionTaskStatus.VOIDED, user["id"], payload.get("void_reason"), task_id),
    )
    audit("void_task", "inspection_task", task_id, user["id"], payload)
    return ok(query_one("SELECT * FROM inspection_tasks WHERE id = ?", (task_id,)))


@app.get("/api/v1/rectification-items")
def list_rectifications(task_id: int | None = None, project_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    rows = query_all("SELECT * FROM rectification_items ORDER BY id")
    rows = filter_task_scoped_rows(rows, user)
    if task_id:
        rows = [row for row in rows if row["inspection_task_id"] == task_id]
    if project_id:
        rows = [row for row in rows if row["project_id"] == project_id]
    return ok({"items": rows})


@app.post("/api/v1/rectification-items/{rectification_id}/mark-done")
def mark_rectification_done(rectification_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    require_rectification_scope(user, rectification_id)
    with transaction():
        execute(
            "UPDATE rectification_items SET marked_done_by = ?, marked_done_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"], rectification_id),
        )
        audit("mark_rectification_done", "rectification_item", rectification_id, user["id"])
    return ok(query_one("SELECT * FROM rectification_items WHERE id = ?", (rectification_id,)))


@app.post("/api/v1/rectification-items/{rectification_id}/undo-done")
def undo_rectification_done(rectification_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    item = require_rectification_scope(user, rectification_id)
    task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (item["inspection_task_id"],))
    if task["status"] != InspectionTaskStatus.RECTIFYING:
        raise BusinessError("RECTIFICATION_UNDO_FORBIDDEN", "复查触发后不能撤销整改完成")
    execute(
        "UPDATE rectification_items SET marked_done_by = NULL, marked_done_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (rectification_id,),
    )
    return ok(query_one("SELECT * FROM rectification_items WHERE id = ?", (rectification_id,)))


@app.get("/api/v1/followup-items")
def list_followups(task_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    rows = query_all("SELECT * FROM followup_items ORDER BY id")
    rows = filter_task_scoped_rows(rows, user)
    if task_id:
        rows = [row for row in rows if row["inspection_task_id"] == task_id]
    return ok({"items": rows})


@app.post("/api/v1/followup-items/{followup_id}/close")
def close_followup(followup_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    require_followup_scope(user, followup_id)
    execute("UPDATE followup_items SET closed_by = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"], followup_id))
    return ok(query_one("SELECT * FROM followup_items WHERE id = ?", (followup_id,)))


@app.post("/api/v1/inspection-tasks/{task_id}/trigger-recheck")
def trigger_recheck(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    task = require_task_scope(user, task_id)
    if task["status"] != InspectionTaskStatus.RECTIFYING:
        raise BusinessError("TASK_NOT_RECTIFYING", "任务不在整改中，不能触发复查")
    current_round = row_or_404(
        "SELECT * FROM inspection_rounds WHERE inspection_task_id = ? AND round_no = ?",
        (task_id, task["current_round_no"]),
        "ROUND_NOT_FOUND",
        "当前轮不存在",
    )
    if current_round["status"] != InspectionRoundStatus.ARCHIVED:
        raise BusinessError("LATEST_ROUND_NOT_ARCHIVED", "最新轮次未归档")
    undone = query_all("SELECT id FROM rectification_items WHERE inspection_task_id = ? AND marked_done_at IS NULL", (task_id,))
    if undone:
        raise BusinessError("RECTIFICATION_NOT_DONE", "存在未完成整改项")
    fail_items = query_all(
        "SELECT * FROM inspection_items WHERE inspection_round_id = ? AND final_result = ? ORDER BY sort_order",
        (current_round["id"], InspectionResult.FAIL),
    )
    with transaction():
        new_round_no = task["current_round_no"] + 1
        round_cur = execute(
            "INSERT INTO inspection_rounds(inspection_task_id, round_no, status) VALUES (?, ?, ?)",
            (task_id, new_round_no, InspectionRoundStatus.RUNNING),
        )
        snapshot = query_one("SELECT * FROM rule_snapshots WHERE inspection_task_id = ?", (task_id,))
        business_snapshot = from_json(snapshot["business_rule_snapshot_json"], [])
        execution_snapshot = from_json(snapshot["auto_check_execution_rule_snapshot_json"], [])
        generate_items_for_round(task_id, round_cur.lastrowid, business_snapshot, execution_snapshot, {item["source_rule_code"] for item in fail_items})
        execute("UPDATE inspection_tasks SET status = ?, current_round_no = ?, last_operated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionTaskStatus.RUNNING, new_round_no, task_id))
        audit("trigger_recheck", "inspection_task", task_id, user["id"], {"new_round_no": new_round_no})
    return ok(
        {
            "inspection_task_id": task_id,
            "task_status": InspectionTaskStatus.RUNNING.value,
            "new_round_id": round_cur.lastrowid,
            "new_round_no": new_round_no,
            "generated_items_count": len(fail_items),
        }
    )


@app.get("/api/v1/reports")
def list_reports(
    project_id: int | None = None,
    qg_node_id: int | None = None,
    overall_result: str | None = None,
    generated_by: int | None = None,
    generated_from: str | None = None,
    generated_to: str | None = None,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    require_business_scope(user)
    rows = query_all("SELECT * FROM inspection_reports ORDER BY id DESC")
    rows = filter_task_scoped_rows(rows, user)
    if project_id:
        rows = [row for row in rows if row["project_id"] == project_id]
    if qg_node_id:
        rows = [row for row in rows if row["qg_node_id"] == qg_node_id]
    if overall_result:
        rows = [row for row in rows if row["overall_result"] == overall_result]
    if generated_by:
        rows = [row for row in rows if row["generated_by"] == generated_by]
    if generated_from:
        rows = [row for row in rows if row["generated_at"] >= generated_from]
    if generated_to:
        rows = [row for row in rows if row["generated_at"] <= generated_to]
    return ok({"items": rows})


@app.get("/api/v1/reports/{report_id}")
def get_report(report_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    report = require_report_scope(user, report_id)
    report["summary_json"] = from_json(report["summary_json"], {})
    report["project"] = query_one("SELECT * FROM projects WHERE id = ?", (report["project_id"],))
    report["qg_node"] = query_one("SELECT * FROM qg_nodes WHERE id = ?", (report["qg_node_id"],))
    report["rule_snapshot"] = query_one(
        "SELECT * FROM rule_snapshots WHERE inspection_task_id = ?",
        (report["inspection_task_id"],),
    )
    if report["rule_snapshot"]:
        report["rule_snapshot"]["business_rule_snapshot_json"] = from_json(report["rule_snapshot"]["business_rule_snapshot_json"], [])
        report["rule_snapshot"]["auto_check_execution_rule_snapshot_json"] = from_json(report["rule_snapshot"]["auto_check_execution_rule_snapshot_json"], [])
    items = query_all("SELECT * FROM report_items WHERE report_id = ? ORDER BY sort_order", (report_id,))
    for item in items:
        item["engineer_decision_snapshot"] = from_json(item["engineer_decision_snapshot"], {})
        item["process_records_json"] = from_json(item["process_records_json"], [])
    report["items"] = items
    return ok(report)


@app.get("/api/v1/audit-logs")
def list_audit_logs(user: dict = Depends(current_user)) -> dict[str, Any]:
    require_permissions(user, {Permission.SUPER_ADMIN})
    return ok({"items": query_all("SELECT * FROM audit_logs ORDER BY id DESC")})


@app.get("/api/v1/inspection-items/{item_id}/auto-check-results")
def list_auto_check_results(item_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    require_item_scope(user, item_id)
    rows = query_all("SELECT * FROM auto_check_results WHERE inspection_item_id = ? ORDER BY attempt_no", (item_id,))
    for row in rows:
        row["execution_rule_snapshot"] = from_json(row["execution_rule_snapshot"], {})
        row["raw_result_json"] = from_json(row["raw_result_json"], {})
    return ok({"items": rows})
