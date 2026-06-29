from enum import StrEnum


class Permission(StrEnum):
    SUPER_ADMIN = "super_admin"
    INSPECTION_ENGINEER = "inspection_engineer"
    RULES_ADMIN = "rules_admin"
    PROJECT_ADMIN = "project_admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ProjectStatus(StrEnum):
    NORMAL = "normal"
    DELETED = "deleted"


class RuleVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class RuleItemType(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    SYSTEM = "system"
    INHERIT = "inherit"


class InspectionTaskStatus(StrEnum):
    RUNNING = "running"
    RECTIFYING = "rectifying"
    COMPLETED = "completed"
    VOIDED = "voided"


class InspectionRoundStatus(StrEnum):
    RUNNING = "running"
    ARCHIVED = "archived"


class InspectionItemStatus(StrEnum):
    PENDING = "pending"
    MANUAL_REQUIRED = "manual_required"
    AUTO_COMPLETED = "auto_completed"
    CONFIRMED = "confirmed"
    INHERITED = "inherited"


class InspectionResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"
    NA = "na"
    INHERIT = "inherit"


class ReportOverallResult(StrEnum):
    NO_GO = "NO_GO"
    C_GO = "C_GO"
    FULL_GO = "FULL_GO"


class AutoCheckStatus(StrEnum):
    SUCCESS = "success"


class AutoExecutionMode(StrEnum):
    FILE_EXISTENCE = "file_existence"


class AdapterType(StrEnum):
    VDRIVE = "vdrive"
    MOCK = "mock"


class SystemSettingKey(StrEnum):
    AUTO_CHECK_ENABLED = "auto_check_enabled"
