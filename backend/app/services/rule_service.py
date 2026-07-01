from typing import Any
from sqlite3 import IntegrityError

from app.core.database import execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import Permission, RuleItemType, RuleVersionStatus
from app.core.exceptions import BusinessError
from app.repositories.common import audit, row_or_404
from app.services.permission_service import require_permissions, require_rule_read_permissions


RULE_CHANGE_FIELDS = (
    "item_name",
    "item_type",
    "check_type",
    "checklist_requirement",
    "owner_dept",
    "is_apqp",
    "is_active",
    "sort_order",
)

RULE_CHANGE_FIELD_LABELS = {
    "item_name": "检查项名称",
    "item_type": "检查项类型",
    "check_type": "检查方式",
    "checklist_requirement": "Checklist 要求",
    "owner_dept": "责任方",
    "is_apqp": "APQP",
    "is_active": "启用状态",
    "sort_order": "排序",
}


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


def logged_rule_change_details(version_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        """
        SELECT rule_code, item_name, item_type, change_type, change_summary, change_detail_json
        FROM business_rule_change_logs
        WHERE business_rule_version_id = ?
        ORDER BY id
        """,
        (version_id,),
    )
    for row in rows:
        row["change_details"] = from_json(row.pop("change_detail_json"), [])
    return rows


def was_published_in_release_batch(version_id: int) -> bool:
    row = query_one(
        "SELECT id FROM business_rule_release_batch_items WHERE new_version_id = ? LIMIT 1",
        (version_id,),
    )
    return bool(row)


def rule_version_change_details(version_id: int) -> list[dict[str, Any]]:
    logged = logged_rule_change_details(version_id)
    if logged:
        return logged
    if was_published_in_release_batch(version_id):
        return []
    rules = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order, id", (version_id,))
    details = []
    for rule in rules:
        details.append(
            {
                "rule_code": rule["rule_code"],
                "item_name": rule["item_name"],
                "item_type": rule["item_type"],
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
                business_rule_version_id, rule_code, item_name, item_type,
                check_type, checklist_requirement, owner_dept, is_apqp, is_active, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_version_id,
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
                    business_check_rule_id, execution_mode, adapter_type,
                    config_json, is_enabled, created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_rule_id,
                    execution_rule["execution_mode"],
                    execution_rule["adapter_type"],
                    execution_rule["config_json"],
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
    row_or_404("SELECT * FROM qg_nodes WHERE id = ?", (qg_node_id,), "QG_NODE_NOT_FOUND", "QG 节点不存在")
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


def current_published_rule_version(qg_node_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT * FROM business_rule_versions
        WHERE qg_node_id = ? AND status = ?
        ORDER BY published_at DESC, id DESC LIMIT 1
        """,
        (qg_node_id, RuleVersionStatus.PUBLISHED),
    )


def draft_rule_versions() -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT v.*, q.node_code
        FROM business_rule_versions v
        JOIN qg_nodes q ON q.id = v.qg_node_id
        WHERE v.status = ?
        ORDER BY q.sort_order, v.id
        """,
        (RuleVersionStatus.DRAFT,),
    )


def rules_by_code(version_id: int | None) -> dict[str, dict[str, Any]]:
    if not version_id:
        return {}
    rows = query_all("SELECT * FROM business_check_rules WHERE business_rule_version_id = ? ORDER BY sort_order, id", (version_id,))
    return {row["rule_code"]: row for row in rows}


def normalized_rule_value(value: Any) -> Any:
    return None if value == "" else value


def rule_field_diffs(old_rule: dict[str, Any], draft_rule: dict[str, Any]) -> list[dict[str, Any]]:
    diffs = []
    for field in RULE_CHANGE_FIELDS:
        old_value = normalized_rule_value(old_rule.get(field))
        new_value = normalized_rule_value(draft_rule.get(field))
        if old_value == new_value:
            continue
        diffs.append(
            {
                "field": field,
                "label": RULE_CHANGE_FIELD_LABELS[field],
                "old_value": old_value,
                "new_value": new_value,
            }
        )
    return diffs


def change_summary_for(
    change_type: str,
    old_rule: dict[str, Any] | None,
    draft_rule: dict[str, Any] | None,
    change_details: list[dict[str, Any]] | None = None,
) -> str:
    rule = draft_rule or old_rule or {}
    name = rule.get("item_name") or rule.get("rule_code") or "检查项"
    if change_type == "added":
        return f"新增「{name}」"
    if change_type == "modified":
        changed_labels = "、".join(detail["label"] for detail in change_details or [])
        return f"{changed_labels or '规则内容'}更新"
    if change_type == "disabled":
        return f"停用「{name}」"
    if change_type == "removed":
        return f"删除「{name}」"
    return f"变更「{name}」"


def rule_changes_between_versions(
    qg_node_id: int,
    node_code: str,
    old_version: dict[str, Any] | None,
    draft_version: dict[str, Any],
) -> list[dict[str, Any]]:
    old_rules = rules_by_code(old_version["id"] if old_version else None)
    draft_rules = rules_by_code(draft_version["id"])
    changes: list[dict[str, Any]] = []
    for rule_code, draft_rule in draft_rules.items():
        old_rule = old_rules.get(rule_code)
        change_details: list[dict[str, Any]] = []
        if not old_rule:
            change_type = "added"
        elif old_rule.get("is_active") and not draft_rule.get("is_active"):
            change_type = "disabled"
            change_details = rule_field_diffs(old_rule, draft_rule)
        else:
            change_details = rule_field_diffs(old_rule, draft_rule)
            if not change_details:
                continue
            change_type = "modified"
        changes.append(
            {
                "qg_node_id": qg_node_id,
                "node_code": node_code,
                "business_rule_version_id": draft_version["id"],
                "rule_code": rule_code,
                "item_name": draft_rule["item_name"],
                "item_type": draft_rule.get("item_type"),
                "change_type": change_type,
                "change_summary": change_summary_for(change_type, old_rule, draft_rule, change_details),
                "change_details": change_details,
            }
        )
    for rule_code, old_rule in old_rules.items():
        if rule_code in draft_rules:
            continue
        changes.append(
            {
                "qg_node_id": qg_node_id,
                "node_code": node_code,
                "business_rule_version_id": draft_version["id"],
                "rule_code": rule_code,
                "item_name": old_rule["item_name"],
                "item_type": old_rule.get("item_type"),
                "change_type": "removed",
                "change_summary": change_summary_for("removed", old_rule, None),
                "change_details": [],
            }
        )
    return changes


def build_rule_release_draft() -> dict[str, Any]:
    nodes = []
    version_changes = []
    flat_changes = []
    for draft in draft_rule_versions():
        old_version = current_published_rule_version(draft["qg_node_id"])
        old_version_no = old_version["version_no"] if old_version else None
        changes = rule_changes_between_versions(draft["qg_node_id"], draft["node_code"], old_version, draft)
        node_preview = {
            "qg_node_id": draft["qg_node_id"],
            "node_code": draft["node_code"],
            "old_version_id": old_version["id"] if old_version else None,
            "old_version_no": old_version_no,
            "new_version_id": draft["id"],
            "new_version_no": draft["version_no"],
            "changes": changes,
        }
        nodes.append(node_preview)
        version_changes.append(
            {
                "qg_node_id": draft["qg_node_id"],
                "node_code": draft["node_code"],
                "old_version_id": old_version["id"] if old_version else None,
                "old_version_no": old_version_no,
                "new_version_id": draft["id"],
                "new_version_no": draft["version_no"],
            }
        )
        flat_changes.extend(changes)
    return {
        "has_draft": bool(nodes),
        "nodes": nodes,
        "version_changes": version_changes,
        "changes": flat_changes,
    }


def get_rule_release_draft(user: dict[str, Any]) -> dict[str, Any]:
    require_rule_read_permissions(user)
    return build_rule_release_draft()


def next_release_batch_no() -> str:
    row = query_one("SELECT COUNT(*) AS total FROM business_rule_release_batches")
    return f"RB{(row['total'] if row else 0) + 1:04d}"


def publish_rule_release_batch(payload: dict | None, user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    change_summary = (payload or {}).get("change_summary")
    with transaction():
        preview = build_rule_release_draft()
        if not preview["nodes"]:
            raise BusinessError("NO_RULE_RELEASE_DRAFT", "当前没有未发布规则变更")
        batch_cur = execute(
            """
            INSERT INTO business_rule_release_batches(batch_no, change_summary, published_by)
            VALUES (?, ?, ?)
            """,
            (next_release_batch_no(), change_summary, user["id"]),
        )
        batch_id = batch_cur.lastrowid
        for node in preview["nodes"]:
            execute(
                """
                INSERT INTO business_rule_release_batch_items(
                    release_batch_id, qg_node_id, old_version_id, new_version_id,
                    old_version_no, new_version_no
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    node["qg_node_id"],
                    node["old_version_id"],
                    node["new_version_id"],
                    node["old_version_no"],
                    node["new_version_no"],
                ),
            )
            execute(
                "UPDATE business_rule_versions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE qg_node_id = ? AND status = ?",
                (RuleVersionStatus.DEPRECATED, node["qg_node_id"], RuleVersionStatus.PUBLISHED),
            )
            if change_summary:
                execute(
                    "UPDATE business_rule_versions SET change_summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (change_summary, node["new_version_id"]),
                )
            status_update = execute(
                """
                UPDATE business_rule_versions
                SET status = ?, published_by = ?, published_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
                """,
                (RuleVersionStatus.PUBLISHED, user["id"], node["new_version_id"], RuleVersionStatus.DRAFT),
            )
            if status_update.rowcount != 1:
                raise BusinessError("RULE_VERSION_NOT_DRAFT", "只有草稿版本可发布")
            for change in node["changes"]:
                execute(
                    """
                    INSERT INTO business_rule_change_logs(
                        release_batch_id, qg_node_id, business_rule_version_id, rule_code,
                        item_name, item_type, change_type, change_summary, change_detail_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        change["qg_node_id"],
                        change["business_rule_version_id"],
                        change["rule_code"],
                        change["item_name"],
                        change.get("item_type"),
                        change["change_type"],
                        change.get("change_summary"),
                        to_json(change.get("change_details", [])),
                    ),
                )
        audit("publish_rule_release_batch", "business_rule_release_batch", batch_id, user["id"], payload or {})
    return get_rule_release_batch(batch_id)


def get_rule_release_batch(batch_id: int) -> dict[str, Any]:
    batch = row_or_404(
        "SELECT * FROM business_rule_release_batches WHERE id = ?",
        (batch_id,),
        "RULE_RELEASE_BATCH_NOT_FOUND",
        "规则发布批次不存在",
    )
    items = query_all(
        """
        SELECT i.*, q.node_code
        FROM business_rule_release_batch_items i
        JOIN qg_nodes q ON q.id = i.qg_node_id
        WHERE i.release_batch_id = ?
        ORDER BY q.sort_order, i.id
        """,
        (batch_id,),
    )
    changes = query_all(
        """
        SELECT c.*, q.node_code
        FROM business_rule_change_logs c
        JOIN qg_nodes q ON q.id = c.qg_node_id
        WHERE c.release_batch_id = ?
        ORDER BY q.sort_order, c.id
        """,
        (batch_id,),
    )
    for change in changes:
        change["change_details"] = from_json(change.pop("change_detail_json"), [])
    for item in items:
        item["changes"] = [change for change in changes if change["qg_node_id"] == item["qg_node_id"]]
    return {
        **batch,
        "status": "published",
        "items": items,
        "changes": changes,
    }


def next_business_rule_code(version_id: int) -> str:
    prefix = f"BR-{version_id}-"
    rows = query_all(
        "SELECT rule_code FROM business_check_rules WHERE business_rule_version_id = ? AND rule_code LIKE ?",
        (version_id, f"{prefix}%"),
    )
    suffixes = []
    for row in rows:
        suffix = row["rule_code"].removeprefix(prefix)
        if suffix.isdigit():
            suffixes.append(int(suffix))
    return f"{prefix}{max(suffixes, default=0) + 1:04d}"


def next_business_rule_sort_order(version_id: int) -> int:
    row = query_one(
        "SELECT MAX(sort_order) AS max_sort_order FROM business_check_rules WHERE business_rule_version_id = ?",
        (version_id,),
    )
    return int(row["max_sort_order"] or 0) + 1


def create_business_rule(version_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    version = row_or_404("SELECT * FROM business_rule_versions WHERE id = ?", (version_id,), "RULE_VERSION_NOT_FOUND", "规则版本不存在")
    if version["status"] != RuleVersionStatus.DRAFT:
        raise BusinessError("RULE_VERSION_NOT_DRAFT", "只有草稿规则版本可编辑")
    item_type = payload.get("item_type", RuleItemType.MANUAL)
    check_type = payload.get("check_type", RuleItemType.MANUAL)
    sort_order = payload.get("sort_order")
    if sort_order is None:
        sort_order = next_business_rule_sort_order(version_id)
    cur = execute(
        """
        INSERT INTO business_check_rules(
            business_rule_version_id, rule_code, item_name, item_type,
            check_type, checklist_requirement, owner_dept, is_apqp, is_active, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            payload.get("rule_code") or next_business_rule_code(version_id),
            payload["item_name"],
            item_type,
            check_type,
            payload.get("checklist_requirement"),
            payload.get("owner_dept"),
            1 if payload.get("is_apqp") else 0,
            1 if payload.get("is_active", True) else 0,
            sort_order,
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
    try:
        cur = execute(
            """
            INSERT INTO auto_check_execution_rules(
                business_check_rule_id, execution_mode, adapter_type,
                config_json, is_enabled, created_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                payload["execution_mode"],
                payload["adapter_type"],
                to_json(payload.get("config_json", {})),
                1 if payload.get("is_enabled", True) else 0,
                user["id"],
            ),
        )
    except IntegrityError as exc:
        raise BusinessError("AUTO_RULE_EXECUTION_EXISTS", "一个检查项只能配置一条自动执行规则") from exc
    audit("create_execution_rule", "auto_check_execution_rule", cur.lastrowid, user["id"], payload)
    return query_one("SELECT * FROM auto_check_execution_rules WHERE id = ?", (cur.lastrowid,))


def update_execution_rule(execution_rule_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    require_permissions(user, {Permission.RULES_ADMIN})
    ensure_rule_version_draft_for_execution_rule(execution_rule_id)
    for field in ("execution_mode", "adapter_type"):
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
