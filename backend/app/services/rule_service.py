from typing import Any

from app.core.database import execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import Permission, RuleItemType, RuleVersionStatus
from app.core.exceptions import BusinessError
from app.repositories.common import audit, row_or_404
from app.services.permission_service import require_permissions, require_rule_read_permissions


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


def rule_version_detail(version_id: int) -> dict[str, Any]:
    version = row_or_404("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,), "RULE_VERSION_NOT_FOUND", "规则版本不存在")
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order", (version_id,))
    for rule in rules:
        rule["auto_check_execution_rules"] = query_all(
            "SELECT * FROM auto_check_execution_rules WHERE business_check_rule_id = ? ORDER BY id",
            (rule["id"],),
        )
    detail = serialize_rule_version(version)
    detail["business_check_rules"] = rules
    return detail


def next_rule_version_no(qg_node_id: int) -> str:
    existing = {
        row["version_no"]
        for row in query_all("SELECT version_no FROM business_rule_versions WHERE qg_node_id = ?", (qg_node_id,))
    }
    numeric_versions = [
        int(version_no[1:])
        for version_no in existing
        if version_no.startswith("V") and version_no[1:].isdigit()
    ]
    number = max(numeric_versions, default=len(existing)) + 1
    while True:
        candidate = f"V{number:02d}"
        if candidate not in existing:
            return candidate
        number += 1


def copy_business_rules_to_draft(source_version_id: int, draft_version_id: int, actor_id: int) -> None:
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order, id", (source_version_id,))
    for rule in rules:
        cur = execute(
            """
            INSERT INTO business_check_rules(
                business_rule_version_id, qg_node_id, rule_code, item_name, item_type,
                check_type, checklist_requirement, owner_dept, is_apqp, is_active, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_version_id,
                rule["qg_node_id"],
                rule["rule_code"],
                rule["item_name"],
                rule["item_type"],
                rule["check_type"],
                rule.get("checklist_requirement"),
                rule.get("owner_dept"),
                rule["is_apqp"],
                rule["is_active"],
                rule["sort_order"],
            ),
        )
        draft_rule_id = cur.lastrowid
        execution_rules = query_all(
            "SELECT * FROM auto_check_execution_rules WHERE business_check_rule_id = ? ORDER BY id",
            (rule["id"],),
        )
        for execution_rule in execution_rules:
            execute(
                """
                INSERT INTO auto_check_execution_rules(
                    business_check_rule_id, execution_code, execution_mode, adapter_type,
                    config_json, config_version, is_enabled, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_rule_id,
                    execution_rule["execution_code"],
                    execution_rule["execution_mode"],
                    execution_rule["adapter_type"],
                    execution_rule["config_json"],
                    execution_rule["config_version"],
                    execution_rule["is_enabled"],
                    actor_id,
                ),
            )


def list_rule_versions(qg_node_id: int | None, status: str | None, user: dict[str, Any]) -> dict[str, Any]:
    require_rule_read_permissions(user)
    rows = query_all("SELECT * FROM business_rule_versions ORDER BY id DESC")
    if qg_node_id:
        rows = [row for row in rows if row["qg_node_id"] == qg_node_id]
    if status:
        rows = [row for row in rows if row["status"] == status]
    return {"items": [serialize_rule_version(row) for row in rows]}


def create_rule_version(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    cur = execute(
        "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
        (payload["qg_node_id"], payload["version_no"], payload.get("change_summary"), user["id"]),
    )
    audit("create_rule_version", "business_rule_version", cur.lastrowid, user["id"], payload)
    return serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (cur.lastrowid,)))


def get_rule_version(version_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_rule_read_permissions(user)
    return rule_version_detail(version_id)


def prepare_editable_rule_version(qg_node_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    row_or_404("SELECT * FROM qg_nodes WHERE id = ? AND is_active = 1", (qg_node_id,), "QG_NODE_NOT_FOUND", "QG 节点不存在")
    with transaction():
        draft = query_one(
            "SELECT * FROM business_rule_versions WHERE qg_node_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
            (qg_node_id, RuleVersionStatus.DRAFT),
        )
        if draft:
            draft_id = draft["id"]
        else:
            source = query_one(
                """
                SELECT * FROM business_rule_versions
                WHERE qg_node_id = ? AND status = ?
                ORDER BY published_at DESC, id DESC LIMIT 1
                """,
                (qg_node_id, RuleVersionStatus.PUBLISHED),
            )
            version_no = next_rule_version_no(qg_node_id)
            change_summary = f"基于 {source['version_no']} 编辑" if source else "新建规则版本"
            cur = execute(
                "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
                (qg_node_id, version_no, change_summary, user["id"]),
            )
            draft_id = cur.lastrowid
            if source:
                copy_business_rules_to_draft(source["id"], draft_id, user["id"])
            audit(
                "prepare_editable_rule_version",
                "business_rule_version",
                draft_id,
                user["id"],
                {"qg_node_id": qg_node_id, "source_version_id": source["id"] if source else None},
            )
    return rule_version_detail(draft_id)


def create_business_rule(version_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return query_one("SELECT * FROM business_check_rules WHERE id = ?", (cur.lastrowid,))


def update_business_rule(rule_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return query_one("SELECT * FROM business_check_rules WHERE id = ?", (rule_id,))


def create_execution_rule(rule_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
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
    return query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (cur.lastrowid,))


def update_execution_rule(execution_rule_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    for field in ("execution_code", "execution_mode", "adapter_type", "config_version"):
        if field in payload:
            execute(f"UPDATE auto_check_execution_rules SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload[field], execution_rule_id))
    if "config_json" in payload:
        execute("UPDATE auto_check_execution_rules SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (to_json(payload["config_json"]), execution_rule_id))
    if "is_enabled" in payload:
        execute("UPDATE auto_check_execution_rules SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if payload["is_enabled"] else 0, execution_rule_id))
    return query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,))


def enable_execution_rule(execution_rule_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    execute("UPDATE auto_check_execution_rules SET is_enabled = 1 WHERE id = ?", (execution_rule_id,))
    return query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,))


def disable_execution_rule(execution_rule_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    execute("UPDATE auto_check_execution_rules SET is_enabled = 0 WHERE id = ?", (execution_rule_id,))
    return query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (execution_rule_id,))


def publish_rule_version(version_id: int, payload: dict | None, user: dict[str, Any]) -> dict[str, Any]:
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
        change_summary = (payload or {}).get("change_summary")
        if change_summary:
            execute(
                "UPDATE business_rule_versions SET change_summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (change_summary, version_id),
            )
        execute(
            "UPDATE business_rule_versions SET status = ?, published_by = ?, published_at = CURRENT_TIMESTAMP WHERE id = ?",
            (RuleVersionStatus.PUBLISHED, user["id"], version_id),
        )
        audit("publish_rule_version", "business_rule_version", version_id, user["id"], payload or {})
    return serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,)))


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


def deprecate_rule_version(version_id: int, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    execute("UPDATE business_rule_versions SET status = ? WHERE id = ?", (RuleVersionStatus.DEPRECATED, version_id))
    audit("deprecate_rule_version", "business_rule_version", version_id, user["id"])
    return serialize_rule_version(query_one("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,)))


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
