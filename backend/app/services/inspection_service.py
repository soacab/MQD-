from typing import Any

from app.core.database import execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import (
    InspectionItemStatus,
    InspectionResult,
    InspectionRoundStatus,
    InspectionTaskStatus,
    Permission,
    ProjectStatus,
    ReportOverallResult,
    RuleItemType,
    RuleVersionStatus,
)
from app.core.exceptions import BusinessError
from app.repositories.common import audit, row_or_404
from app.services import ai_execution_service, project_service, report_service, rule_service
from app.services.permission_service import (
    filter_task_scoped_rows,
    has_full_business_scope,
    require_business_scope,
    require_followup_scope,
    require_item_scope,
    require_permissions,
    require_rectification_scope,
    require_task_scope,
    task_in_business_scope,
    task_project_is_active,
)


def prepare_inspection_task(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER, Permission.PROJECT_ADMIN})
    vdrive = project_service.parse_vdrive_url(payload.get("vdrive_url", ""))
    project = project_service.find_project_by_vdrive(vdrive)
    project_payload = project_service.project_detail(project) if project else None
    return {
        "vdrive": vdrive,
        "has_history": bool(project),
        "project": project_payload,
        "suggested_project_name": project["project_name"] if project else vdrive["folder_name"],
        "recommended_qg_node": project_service.recommended_qg_node_for_project(project["id"] if project else None),
    }


def ensure_wizard_payload(payload: dict[str, Any]) -> list[str]:
    for field in ("vdrive_url", "project_name", "customer", "receive_date", "qg_node_id"):
        if not payload.get(field):
            raise BusinessError("INSPECTION_TASK_REQUIRED_FIELD", f"缺少必填字段 {field}")
    models = project_service.normalize_models(payload.get("models"))
    if not models:
        raise BusinessError("INSPECTION_TASK_REQUIRED_FIELD", "至少填写 1 个机型")
    return models


def upsert_project_from_task_wizard(payload: dict[str, Any], user: dict[str, Any]) -> int:
    models = ensure_wizard_payload(payload)
    vdrive = project_service.parse_vdrive_url(payload.get("vdrive_url", ""))
    mq_user = query_one("SELECT name FROM users WHERE id = ?", (payload.get("mq_user_id"),))
    project = project_service.find_project_by_vdrive(vdrive)
    if project:
        execute(
            """
            UPDATE projects SET project_name = ?, customer = ?, project_category = ?, bu = ?,
            project_level = ?, mq_user_id = ?, mq_user_name_snapshot = ?, mp_owner = ?,
            group_name = ?, planned_mp_date = ?, production_line = ?, vdrive_url = ?,
            vdrive_folder_guid = ?, vdrive_folder_id = ?, vdrive_folder_name = ?,
            vdrive_folder_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
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
                project["id"],
            ),
        )
        if not query_one("SELECT id FROM project_models WHERE project_id = ? LIMIT 1", (project["id"],)):
            project_service.add_project_order_rows(project["id"], payload["receive_date"], models, user["id"])
        audit("upsert_project_from_task_wizard", "project", project["id"], user["id"], payload)
        return project["id"]

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
    project_service.add_project_order_rows(project_id, payload["receive_date"], models, user["id"])
    audit("create_project_from_task_wizard", "project", project_id, user["id"], payload)
    return project_id


def create_inspection_task_for_project(project_id: int, qg_node_id: int, user: dict[str, Any], audit_payload: dict[str, Any]) -> dict[str, Any]:
    project = row_or_404("SELECT * FROM projects WHERE id = ?", (project_id,), "PROJECT_NOT_FOUND", "项目不存在")
    if project["status"] != ProjectStatus.NORMAL:
        raise BusinessError("PROJECT_DELETED", "已删除项目不能创建点检任务")
    if not project["vdrive_folder_guid"] or not project["vdrive_folder_id"]:
        raise BusinessError("PROJECT_VDRIVE_REQUIRED", "项目缺少 VDrive 文件夹标识")
    version = query_one(
        "SELECT * FROM business_rule_versions WHERE qg_node_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
        (qg_node_id, RuleVersionStatus.PUBLISHED),
    )
    if not version:
        raise BusinessError("PUBLISHED_RULE_VERSION_REQUIRED", "当前 QG 节点没有已发布规则版本")
    active = query_one(
        "SELECT * FROM inspection_tasks WHERE project_id = ? AND qg_node_id = ? AND status IN (?, ?)",
        (project_id, qg_node_id, InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING),
    )
    if active:
        raise BusinessError("ACTIVE_TASK_EXISTS", "同项目同节点已有进行中或整改中任务")

    task_no = f"IT-{project_id}-{qg_node_id}-{version['id']}"
    with transaction():
        cur = execute(
            """
            INSERT INTO inspection_tasks(project_id, qg_node_id, task_no, status, current_round_no, created_by)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (project_id, qg_node_id, task_no, InspectionTaskStatus.RUNNING, user["id"]),
        )
        task_id = cur.lastrowid
        business_snapshot, execution_snapshot = rule_service.build_rule_snapshots(version["id"])
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
            (task_id, project["id"], qg_node_id, f"REP-{task_id}", version["version_no"], user["id"]),
        )
        audit("create_inspection_task", "inspection_task", task_id, user["id"], audit_payload)
    return {
        "inspection_task_id": task_id,
        "project_id": project["id"],
        "qg_node_id": qg_node_id,
        "status": InspectionTaskStatus.RUNNING.value,
        "current_round_no": 1,
        "round_id": round_id,
        "rule_snapshot_id": snapshot_cur.lastrowid,
        "report_id": report_cur.lastrowid,
    }


def create_inspection_task(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    if payload.get("project_id"):
        if not payload.get("qg_node_id"):
            raise BusinessError("INSPECTION_TASK_REQUIRED_FIELD", "缺少必填字段 qg_node_id")
        return create_inspection_task_for_project(int(payload["project_id"]), int(payload["qg_node_id"]), user, payload)
    project_id = upsert_project_from_task_wizard(payload, user)
    return create_inspection_task_for_project(project_id, int(payload["qg_node_id"]), user, payload)


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
            ai_execution_service.run_mock_auto_check(cur.lastrowid, execution_rules_by_business_rule_id[rule["id"]])


def list_inspection_tasks(status: str | None, project_id: int | None, user: dict[str, Any]) -> dict[str, Any]:
    require_business_scope(user)
    rows = query_all("SELECT * FROM inspection_tasks ORDER BY id DESC")
    rows = [row for row in rows if task_project_is_active(row)]
    if not has_full_business_scope(user):
        rows = [row for row in rows if task_in_business_scope(row, user)]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if project_id:
        rows = [row for row in rows if row["project_id"] == project_id]
    return {"items": rows}


def get_inspection_task(task_id: int, user: dict[str, Any]) -> dict[str, Any]:
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
    return task


def current_round_items(task_id: int, user: dict[str, Any]) -> dict[str, Any]:
    task = require_task_scope(user, task_id)
    round_row = row_or_404(
        "SELECT * FROM inspection_rounds WHERE inspection_task_id = ? AND round_no = ?",
        (task_id, task["current_round_no"]),
        "ROUND_NOT_FOUND",
        "当前轮不存在",
    )
    items = query_all("SELECT * FROM inspection_items WHERE inspection_round_id = ? ORDER BY sort_order", (round_row["id"],))
    return {"round_id": round_row["id"], "round_no": round_row["round_no"], "items": items}


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


def dashboard_overview(user: dict[str, Any]) -> dict[str, Any]:
    tasks = scoped_tasks_for_dashboard(user)
    rectifications = filter_task_scoped_rows(query_all("SELECT * FROM rectification_items ORDER BY id"), user)
    followups = filter_task_scoped_rows(query_all("SELECT * FROM followup_items ORDER BY id"), user)

    running = [task for task in tasks if task["status"] == InspectionTaskStatus.RUNNING]
    archive_ready = []
    for task in running:
        progress = task_progress(task["id"])
        if progress["total"] > 0 and progress["pending"] == 0:
            archive_ready.append(task)

    return {
        "running_count": len(running),
        "recheck_count": len([task for task in tasks if task["status"] == InspectionTaskStatus.RECTIFYING]),
        "rectification_count": len([item for item in rectifications if not item["marked_done_at"]]),
        "followup_count": len([item for item in followups if not item["closed_at"]]),
        "archive_ready_count": len(archive_ready),
    }


def dashboard_my_todos(user: dict[str, Any]) -> dict[str, Any]:
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

    return {"items": rows, "total": len(rows)}


def get_inspection_item(item_id: int, user: dict[str, Any]) -> dict[str, Any]:
    item = require_item_scope(user, item_id)
    item["engineer_decisions"] = query_all("SELECT * FROM engineer_decisions WHERE inspection_item_id = ? ORDER BY id", (item_id,))
    item["auto_check_results"] = query_all("SELECT * FROM auto_check_results WHERE inspection_item_id = ? ORDER BY id", (item_id,))
    return item


def ensure_item_mutable(item: dict[str, Any]) -> None:
    task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (item["inspection_task_id"],))
    round_row = query_one("SELECT * FROM inspection_rounds WHERE id = ?", (item["inspection_round_id"],))
    if task["status"] != InspectionTaskStatus.RUNNING or round_row["status"] != InspectionRoundStatus.RUNNING:
        raise BusinessError("ITEM_NOT_MUTABLE", "当前检查项不允许修改")


def convert_to_manual(item_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    item = require_item_scope(user, item_id)
    ensure_item_mutable(item)
    execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.MANUAL_REQUIRED, item_id))
    audit("convert_to_manual", "inspection_item", item_id, user["id"], payload)
    return query_one("SELECT * FROM inspection_items WHERE id = ?", (item_id,))


def confirm_item(item_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return {"item": query_one("SELECT * FROM inspection_items WHERE id = ?", (item_id,)), "decision_id": cur.lastrowid}


def archive_current_round(task_id: int, user: dict[str, Any]) -> dict[str, Any]:
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
        report = report_service.update_after_archive(task_id, round_row, items, overall_result)
        audit("archive_current_round", "inspection_task", task_id, user["id"], {"overall_result": overall_result})
    return {
        "inspection_task_id": task_id,
        "archived_round_no": round_row["round_no"],
        "overall_result": overall_result.value,
        "task_status": task_status.value,
        "generated_rectification_count": rectification_count,
        "generated_followup_count": followup_count,
        "report_id": report["id"],
    }


def generate_work_items(task: dict[str, Any], round_row: dict[str, Any], items: list[dict[str, Any]], actor_id: int) -> tuple[int, int]:
    rectification_count = 0
    followup_count = 0
    for item in items:
        decision = report_service.latest_decision(item["id"]) or {}
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


def void_task(task_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    task = require_task_scope(user, task_id)
    if task["status"] not in (InspectionTaskStatus.RUNNING, InspectionTaskStatus.RECTIFYING):
        raise BusinessError("TASK_CANNOT_BE_VOIDED", "当前状态不能作废")
    execute(
        "UPDATE inspection_tasks SET status = ?, voided_by = ?, voided_at = CURRENT_TIMESTAMP, void_reason = ? WHERE id = ?",
        (InspectionTaskStatus.VOIDED, user["id"], payload.get("void_reason"), task_id),
    )
    audit("void_task", "inspection_task", task_id, user["id"], payload)
    return query_one("SELECT * FROM inspection_tasks WHERE id = ?", (task_id,))


def list_rectifications(task_id: int | None, project_id: int | None, user: dict[str, Any]) -> dict[str, Any]:
    rows = query_all("SELECT * FROM rectification_items ORDER BY id")
    rows = filter_task_scoped_rows(rows, user)
    if task_id:
        rows = [row for row in rows if row["inspection_task_id"] == task_id]
    if project_id:
        rows = [row for row in rows if row["project_id"] == project_id]
    return {"items": rows}


def mark_rectification_done(rectification_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    require_rectification_scope(user, rectification_id)
    with transaction():
        execute(
            "UPDATE rectification_items SET marked_done_by = ?, marked_done_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"], rectification_id),
        )
        audit("mark_rectification_done", "rectification_item", rectification_id, user["id"])
    return query_one("SELECT * FROM rectification_items WHERE id = ?", (rectification_id,))


def undo_rectification_done(rectification_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    item = require_rectification_scope(user, rectification_id)
    task = query_one("SELECT * FROM inspection_tasks WHERE id = ?", (item["inspection_task_id"],))
    if task["status"] != InspectionTaskStatus.RECTIFYING:
        raise BusinessError("RECTIFICATION_UNDO_FORBIDDEN", "复查触发后不能撤销整改完成")
    execute(
        "UPDATE rectification_items SET marked_done_by = NULL, marked_done_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (rectification_id,),
    )
    return query_one("SELECT * FROM rectification_items WHERE id = ?", (rectification_id,))


def list_followups(task_id: int | None, user: dict[str, Any]) -> dict[str, Any]:
    rows = query_all("SELECT * FROM followup_items ORDER BY id")
    rows = filter_task_scoped_rows(rows, user)
    if task_id:
        rows = [row for row in rows if row["inspection_task_id"] == task_id]
    return {"items": rows}


def close_followup(followup_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.INSPECTION_ENGINEER})
    require_followup_scope(user, followup_id)
    execute("UPDATE followup_items SET closed_by = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"], followup_id))
    return query_one("SELECT * FROM followup_items WHERE id = ?", (followup_id,))


def trigger_recheck(task_id: int, user: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "inspection_task_id": task_id,
        "task_status": InspectionTaskStatus.RUNNING.value,
        "new_round_id": round_cur.lastrowid,
        "new_round_no": new_round_no,
        "generated_items_count": len(fail_items),
    }


def list_auto_check_results(item_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_item_scope(user, item_id)
    rows = query_all("SELECT * FROM auto_check_results WHERE inspection_item_id = ? ORDER BY attempt_no", (item_id,))
    for row in rows:
        row["execution_rule_snapshot"] = from_json(row["execution_rule_snapshot"], {})
        row["raw_result_json"] = from_json(row["raw_result_json"], {})
    return {"items": rows}
