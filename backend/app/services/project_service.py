from typing import Any

from app.core.database import execute, query_all, query_one, transaction
from app.core.enums import InspectionTaskStatus, Permission, ProjectStatus
from app.core.exceptions import BusinessError
from app.repositories.common import audit, paginate, row_or_404
from app.services.permission_service import (
    has_full_business_scope,
    require_business_scope,
    require_permissions,
    require_project_scope,
    require_rule_read_permissions,
    task_in_business_scope,
    project_in_business_scope,
)
from app.vdrive import validate_vdrive_folder_link


def parse_vdrive_url(url: str) -> dict[str, Any]:
    return validate_vdrive_folder_link(url)


def normalize_models(raw_models: Any) -> list[str]:
    if isinstance(raw_models, str):
        models = [item.strip() for item in raw_models.split(",")]
    else:
        models = [str(item).strip() for item in raw_models or []]
    return [model for model in models if model]


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


def list_projects(
    keyword: str | None,
    qg_node_id: int | None,
    status: str | None,
    mq_user_id: int | None,
    page: int,
    page_size: int,
    user: dict[str, Any],
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
    return paginate([project_detail(row) for row in rows], page, page_size)


def archive_date_upper_bound(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value} 23:59:59" if len(value) == 10 else value


def archive_keyword_matches(row: dict[str, Any], keyword: str | None) -> bool:
    if not keyword:
        return True
    target = keyword.lower()
    text_parts = [row["project_name"], row.get("customer") or "", *row["models"]]
    return any(target in str(part).lower() for part in text_parts)


def build_archive_project_rows(user: dict[str, Any]) -> list[dict[str, Any]]:
    require_business_scope(user)
    reports = query_all(
        """
        SELECT * FROM inspection_reports
        WHERE overall_result IS NOT NULL
        ORDER BY last_modified_at DESC, id DESC
        """
    )
    rows = []
    seen_project_ids: set[int] = set()
    for report in reports:
        if report["project_id"] in seen_project_ids:
            continue
        project = query_one("SELECT * FROM projects WHERE id = ?", (report["project_id"],))
        task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (report["inspection_task_id"],))
        qg_node = query_one("SELECT * FROM qg_nodes WHERE id = ?", (report["qg_node_id"],))
        if not project or not task or not qg_node:
            continue
        if project["status"] == ProjectStatus.DELETED:
            seen_project_ids.add(project["id"])
            continue
        if not has_full_business_scope(user) and not task_in_business_scope(task, user):
            continue
        model_rows = query_all("SELECT model_name FROM project_models WHERE project_id = ? ORDER BY id", (project["id"],))
        mq_user_id = project.get("mq_user_id") or task.get("created_by")
        mq_user = query_one("SELECT name FROM users WHERE id = ?", (mq_user_id,)) if mq_user_id else None
        rows.append(
            {
                "project_id": project["id"],
                "project_name": project["project_name"],
                "customer": project["customer"],
                "models": [row["model_name"] for row in model_rows],
                "project_created_at": project["created_at"],
                "qg_node": qg_node,
                "overall_result": report["overall_result"],
                "report_last_modified_at": report["last_modified_at"],
                "mq_user_id": mq_user_id,
                "mq_user_name": project.get("mq_user_name_snapshot") or (mq_user["name"] if mq_user else None),
                "latest_report_id": report["id"],
                "inspection_task_id": report["inspection_task_id"],
            }
        )
        seen_project_ids.add(project["id"])
    return rows


def list_archive_projects(
    keyword: str | None,
    mq_user_id: int | None,
    qg_node_id: int | None,
    overall_result: str | None,
    modified_from: str | None,
    modified_to: str | None,
    page: int,
    page_size: int,
    user: dict[str, Any],
) -> dict[str, Any]:
    rows = build_archive_project_rows(user)
    upper_bound = archive_date_upper_bound(modified_to)
    if keyword:
        rows = [row for row in rows if archive_keyword_matches(row, keyword)]
    if mq_user_id:
        rows = [row for row in rows if row["mq_user_id"] == mq_user_id]
    if qg_node_id:
        rows = [row for row in rows if row["qg_node"]["id"] == qg_node_id]
    if overall_result:
        rows = [row for row in rows if row["overall_result"] == overall_result]
    if modified_from:
        rows = [row for row in rows if row["report_last_modified_at"] >= modified_from]
    if upper_bound:
        rows = [row for row in rows if row["report_last_modified_at"] <= upper_bound]
    return paginate(rows, page, page_size)


def find_project_by_vdrive(vdrive: dict[str, Any]) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT * FROM projects
        WHERE status = ? AND vdrive_folder_guid = ?
        ORDER BY id DESC LIMIT 1
        """,
        (ProjectStatus.NORMAL, vdrive["folder_guid"]),
    )


def first_qg_node() -> dict[str, Any] | None:
    return query_one("SELECT * FROM qg_nodes ORDER BY sort_order LIMIT 1")


def recommended_qg_node_for_project(project_id: int | None) -> dict[str, Any] | None:
    if project_id is None:
        return first_qg_node()
    latest_task = query_one(
        """
        SELECT q.sort_order FROM inspection_tasks t
        JOIN qg_nodes q ON q.id = t.qg_node_id
        WHERE t.project_id = ? AND t.status != ?
        ORDER BY t.id DESC LIMIT 1
        """,
        (project_id, InspectionTaskStatus.VOIDED),
    )
    if not latest_task:
        return first_qg_node()
    return (
        query_one(
            """
            SELECT * FROM qg_nodes
            WHERE sort_order > ?
            ORDER BY sort_order LIMIT 1
            """,
            (latest_task["sort_order"],),
        )
        or first_qg_node()
    )


def get_project(project_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_business_scope(user)
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    require_project_scope(user, project)
    return project_detail(project)


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


def create_project(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,)))


def update_project(project_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] == ProjectStatus.DELETED:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能编辑")
    fields = ["project_name", "customer", "project_category", "bu", "project_level", "mq_user_id", "mp_owner", "group_name", "planned_mp_date", "production_line"]
    for field in fields:
        if field in payload:
            execute(f"UPDATE projects SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload[field], project_id))
    audit("update_project", "project", project_id, user["id"], payload)
    return project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,)))


def update_project_vdrive(project_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,)))


def add_project_order(project_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER, Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    require_project_scope(user, project)
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能加单")
    active_task = query_one(
        "SELECT id FROM inspection_tasks WHERE project_id = ? AND status IN (?, ?) LIMIT 1",
        (project_id, InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING),
    )
    if active_task:
        raise BusinessError("PROJECT_HAS_ACTIVE_TASK", "项目存在进行中或整改中任务，不能加单")
    models = normalize_models(payload.get("models"))
    if not models:
        raise BusinessError("PROJECT_ORDER_MODEL_REQUIRED", "至少填写 1 个新增机型")
    order_id = add_project_order_rows(project_id, payload["receive_date"], models, user["id"])
    audit("add_project_order", "project", project_id, user["id"], payload)
    return {"id": order_id}


def delete_project(project_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.PROJECT_ADMIN})
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能重复作废")
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
    return project_detail(query_one("SELECT * FROM projects WHERE id = ?", (project_id,)))


def list_qg_nodes(user: dict[str, Any]) -> dict[str, Any]:
    require_rule_read_permissions(user)
    return {"items": query_all("SELECT * FROM qg_nodes ORDER BY sort_order")}
