from typing import Any

from app.core.database import execute, from_json, query_all, query_one, to_json
from app.core.enums import InspectionResult
from app.services.permission_service import filter_task_scoped_rows, require_business_scope, require_report_scope


def latest_decision(item_id: int) -> dict[str, Any] | None:
    return query_one("SELECT * FROM engineer_decisions WHERE inspection_item_id = ? ORDER BY id DESC LIMIT 1", (item_id,))


def update_after_archive(task_id: int, round_row: dict[str, Any], items: list[dict[str, Any]], overall_result: str) -> dict[str, Any]:
    report = query_one("SELECT * FROM inspection_reports WHERE inspection_task_id = ?", (task_id,))
    archived_round = query_one("SELECT * FROM inspection_rounds WHERE id = ?", (round_row["id"],)) or round_row
    inspected_at = archived_round.get("archived_at") or round_row.get("archived_at") or round_row.get("started_at")
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
            "inspected_at": inspected_at,
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


def list_reports(
    project_id: int | None,
    qg_node_id: int | None,
    overall_result: str | None,
    generated_by: int | None,
    generated_from: str | None,
    generated_to: str | None,
    user: dict[str, Any],
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
    return {"items": rows}


def get_report(report_id: int, user: dict[str, Any]) -> dict[str, Any]:
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
    return report
