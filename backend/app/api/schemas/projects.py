from app.api.schemas.common import StrictRequest


class ValidateVDriveLinkRequest(StrictRequest):
    vdrive_url: str | None = None


class CreateProjectRequest(StrictRequest):
    project_name: str | None = None
    customer: str | None = None
    project_category: str | None = None
    bu: str | None = None
    project_level: str | None = None
    mq_user_id: int | None = None
    mp_owner: str | None = None
    group_name: str | None = None
    planned_mp_date: str | None = None
    production_line: str | None = None
    vdrive_url: str | None = None
    receive_date: str | None = None
    models: list[str] | str | None = None


class UpdateProjectRequest(StrictRequest):
    project_name: str | None = None
    customer: str | None = None
    project_category: str | None = None
    bu: str | None = None
    project_level: str | None = None
    mq_user_id: int | None = None
    mp_owner: str | None = None
    group_name: str | None = None
    planned_mp_date: str | None = None
    production_line: str | None = None


class UpdateProjectVDriveRequest(StrictRequest):
    vdrive_url: str


class AddProjectOrderRequest(StrictRequest):
    receive_date: str
    models: list[str] | str | None = None


class DeleteProjectRequest(StrictRequest):
    confirm_project_name: str | None = None
    delete_reason: str | None = None
