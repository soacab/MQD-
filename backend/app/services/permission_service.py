from typing import Any

from app.core.database import query_all, query_one
from app.core.enums import Permission, ProjectStatus, UserStatus
from app.core.exceptions import BusinessError
from app.repositories.common import row_or_404


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
    if Permission.INSPECTION_ENGINEER not in business_permissions(user):
        return False
    project = query_one("SELECT mq_user_id FROM projects WHERE id = ?", (task["project_id"],))
    if not project:
        return False
    if project["mq_user_id"] is not None:
        return project["mq_user_id"] == user["id"]
    return task["created_by"] == user["id"]


def project_in_business_scope(project_id: int, user: dict[str, Any]) -> bool:
    if has_full_business_scope(user):
        return True
    if Permission.INSPECTION_ENGINEER not in business_permissions(user):
        return False
    project = query_one("SELECT mq_user_id FROM projects WHERE id = ?", (project_id,))
    if not project:
        return False
    if project["mq_user_id"] is not None:
        return project["mq_user_id"] == user["id"]
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
    task = row_or_404("SELECT * FROM inspection_tasks WHERE id = ?", (report["inspection_task_id"],), "TASK_NOT_FOUND", "点检任务不存在")
    if not task_in_business_scope(task, user):
        raise BusinessError("FORBIDDEN", "权限不足", 403)
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
