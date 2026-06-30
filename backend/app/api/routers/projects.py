from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import current_user
from app.api.responses import ok
from app.services import project_service

router = APIRouter()


@router.post("/api/v1/vdrive/validate-folder-link")
def validate_vdrive_link(payload: dict = Body(...), _: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.parse_vdrive_url(payload.get("vdrive_url", "")))


@router.get("/api/v1/projects")
def list_projects(
    keyword: str | None = None,
    qg_node_id: int | None = None,
    status: str | None = None,
    mq_user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    return ok(project_service.list_projects(keyword, qg_node_id, status, mq_user_id, page, page_size, user))


@router.get("/api/v1/archive-projects")
def list_archive_projects(
    keyword: str | None = None,
    mq_user_id: int | None = None,
    qg_node_id: int | None = None,
    overall_result: str | None = None,
    modified_from: str | None = None,
    modified_to: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    return ok(project_service.list_archive_projects(keyword, mq_user_id, qg_node_id, overall_result, modified_from, modified_to, page, page_size, user))


@router.get("/api/v1/projects/{project_id}")
def get_project(project_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.get_project(project_id, user))


@router.post("/api/v1/projects")
def create_project(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.create_project(payload, user))


@router.patch("/api/v1/projects/{project_id}")
def update_project(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.update_project(project_id, payload, user))


@router.post("/api/v1/projects/{project_id}/vdrive-link")
def update_project_vdrive(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.update_project_vdrive(project_id, payload, user))


@router.post("/api/v1/projects/{project_id}/orders")
def add_project_order(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.add_project_order(project_id, payload, user))


@router.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.delete_project(project_id, payload, user))


@router.get("/api/v1/qg-nodes")
def list_qg_nodes(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(project_service.list_qg_nodes(user))
