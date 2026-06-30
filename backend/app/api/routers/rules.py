from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import current_user
from app.api.responses import ok
from app.services import rule_service

router = APIRouter()


@router.get("/api/v1/business-rule-versions")
def list_rule_versions(qg_node_id: int | None = None, status: str | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.list_rule_versions(qg_node_id, status, user))


@router.post("/api/v1/business-rule-versions")
def create_rule_version(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.create_rule_version(payload, user))


@router.get("/api/v1/business-rule-versions/{version_id}")
def get_rule_version(version_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.get_rule_version(version_id, user))


@router.post("/api/v1/qg-nodes/{qg_node_id}/editable-rule-version")
def prepare_editable_rule_version(qg_node_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.prepare_editable_rule_version(qg_node_id, user))


@router.post("/api/v1/business-rule-versions/{version_id}/business-check-rules")
def create_business_rule(version_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.create_business_rule(version_id, payload, user))


@router.patch("/api/v1/business-check-rules/{rule_id}")
def update_business_rule(rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.update_business_rule(rule_id, payload, user))


@router.post("/api/v1/business-check-rules/{rule_id}/auto-check-execution-rules")
def create_execution_rule(rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.create_execution_rule(rule_id, payload, user))


@router.patch("/api/v1/auto-check-execution-rules/{execution_rule_id}")
def update_execution_rule(execution_rule_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.update_execution_rule(execution_rule_id, payload, user))


@router.post("/api/v1/auto-check-execution-rules/{execution_rule_id}/enable")
def enable_execution_rule(execution_rule_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.enable_execution_rule(execution_rule_id, user))


@router.post("/api/v1/auto-check-execution-rules/{execution_rule_id}/disable")
def disable_execution_rule(execution_rule_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.disable_execution_rule(execution_rule_id, user))


@router.post("/api/v1/business-rule-versions/{version_id}/publish")
def publish_rule_version(version_id: int, payload: dict | None = Body(default=None), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.publish_rule_version(version_id, payload, user))


@router.post("/api/v1/business-rule-versions/{version_id}/deprecate")
def deprecate_rule_version(version_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(rule_service.deprecate_rule_version(version_id, user))
