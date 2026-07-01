const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const SESSION_TOKEN_KEY = "checkflow_access_token";

export type ApiResponse<T> = {
  success: boolean;
  data: T;
  message: string;
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(message: string, status: number, code = "API_ERROR", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export type User = {
  id: number;
  uid: string;
  name: string;
  email?: string | null;
  status: string;
  permissions: string[];
};

export type BusinessUserOption = {
  id: number;
  name: string;
  permissions: string[];
};

export type LoginResult = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type ListUsersParams = {
  keyword?: string;
  status?: string;
  permission?: string;
};

export type ListProjectsParams = {
  keyword?: string;
  status?: string;
  qg_node_id?: string;
  mq_user_id?: string;
  page?: string;
  page_size?: string;
};

export type ListArchiveProjectsParams = {
  keyword?: string;
  mq_user_id?: string;
  qg_node_id?: string;
  overall_result?: string;
  modified_from?: string;
  modified_to?: string;
  page?: string;
  page_size?: string;
};

export type UserPayload = {
  uid?: string;
  name: string;
  email?: string;
  status: string;
  permissions: string[];
};

export type Project = {
  id: number;
  project_name: string;
  customer: string;
  project_category?: string | null;
  bu?: string | null;
  project_level?: string | null;
  mq_user_id?: number | null;
  mq_user_name_snapshot?: string | null;
  mp_owner?: string | null;
  group_name?: string | null;
  planned_mp_date?: string | null;
  production_line?: string | null;
  status: string;
  vdrive_url?: string | null;
  vdrive?: {
    url?: string | null;
    folder_guid?: string | null;
    folder_id?: number | null;
    folder_name?: string | null;
    folder_path?: string | null;
  };
  orders?: Array<{ id: number; receive_date: string; created_at?: string | null }>;
  models?: Array<{ id: number; project_order_id?: number; model_name: string }>;
};

export type VDriveValidation = {
  valid: boolean;
  folder_guid: string;
  folder_id: number;
  folder_name: string;
  folder_path: string;
};

export type InspectionTaskPrepare = {
  vdrive: VDriveValidation;
  has_history: boolean;
  project: Project | null;
  suggested_project_name: string;
  recommended_qg_node: QGNode | null;
};

export type QGNode = {
  id: number;
  node_code: string;
  sort_order: number;
};

export type ArchiveProject = {
  project_id: number;
  project_name: string;
  customer: string;
  models: string[];
  project_created_at: string;
  qg_node: QGNode;
  overall_result: string;
  report_last_modified_at: string;
  mq_user_id?: number | null;
  mq_user_name?: string | null;
  latest_report_id: number;
  inspection_task_id: number;
};

export type RuleVersion = {
  id: number;
  qg_node_id: number;
  version_no: string;
  status: string;
  change_summary?: string | null;
  published_by?: number | null;
  published_by_name?: string | null;
  published_at?: string | null;
  is_current?: boolean;
  change_details?: RuleChangeDetail[];
  business_check_rules?: BusinessRule[];
};

export type RuleChangeDetail = {
  rule_code: string;
  item_name: string;
  change_type: string;
  change_summary?: string | null;
};

export type BusinessRule = {
  id: number;
  business_rule_version_id: number;
  rule_code: string;
  item_name: string;
  item_type: string;
  check_type: string;
  checklist_requirement?: string | null;
  owner_dept?: string | null;
  is_apqp: number;
  is_active: number;
  sort_order: number;
  auto_check_execution_rules?: AutoCheckExecutionRule[];
};

export type AutoCheckExecutionRule = {
  id: number;
  business_check_rule_id: number;
  execution_mode: string;
  adapter_type: string;
  is_enabled: number;
};

export type InspectionTask = {
  id?: number;
  inspection_task_id?: number;
  project_id: number;
  qg_node_id: number;
  task_no?: string;
  status: string;
  current_round_no: number;
  summary?: {
    total_items: number;
    confirmed_count: number;
    pending_count: number;
  };
  project?: Project;
  qg_node?: QGNode;
};

export type InspectionItem = {
  id: number;
  inspection_task_id: number;
  inspection_round_id: number;
  source_rule_code: string;
  item_name_snapshot: string;
  item_type_snapshot: string;
  check_type_snapshot: string;
  checklist_requirement_snapshot?: string | null;
  owner_dept_snapshot?: string | null;
  status: string;
  final_result?: string | null;
  engineer_decisions?: Array<Record<string, unknown>>;
  auto_check_results?: Array<Record<string, unknown>>;
};

export type Report = {
  id: number;
  inspection_task_id: number;
  project_id: number;
  qg_node_id: number;
  report_no: string;
  overall_result?: string | null;
  latest_round_no: number;
  business_rule_version_no: string;
  project?: Project;
  qg_node?: QGNode;
  rule_snapshot?: {
    business_rule_snapshot_json?: BusinessRule[];
    auto_check_execution_rule_snapshot_json?: AutoCheckExecutionRule[];
  } | null;
  items?: ReportItem[];
};

export type ReportItem = {
  id: number;
  source_rule_code: string;
  item_name_snapshot: string;
  final_result?: string | null;
  process_records_json: Array<Record<string, unknown>>;
};

export type RectificationItem = {
  id: number;
  inspection_task_id: number;
  project_id: number;
  item_name_snapshot: string;
  problem_desc: string;
  responsible_owner: string;
  planned_finish_date: string;
  marked_done_at?: string | null;
};

export type FollowUpItem = {
  id: number;
  inspection_task_id: number;
  project_id: number;
  item_name_snapshot: string;
  countermeasure: string;
  responsible_owner: string;
  planned_finish_date: string;
  closed_at?: string | null;
};

export type DashboardOverview = {
  running_count: number;
  recheck_count: number;
  rectification_count: number;
  followup_count: number;
  archive_ready_count: number;
};

export type DashboardTodo = {
  type: string;
  target_id: number;
  task_id?: number;
  project_id?: number;
  project_name?: string;
  qg_node?: string;
  title?: string;
  status?: string;
  href: string;
  summary?: string;
  planned_finish_date?: string;
  round_label?: string;
  confirmed_count?: number;
  total_count?: number;
  progress_percent?: number;
  rectification_done_count?: number;
  rectification_total_count?: number;
  rectification_progress_percent?: number;
  mq_user_name?: string;
  mq_user_uid?: string;
  last_operated_at?: string;
  auto_check_status?: {
    label: string;
    value: string;
    tone: string;
  };
};

export type ListResult<T> = {
  items: T[];
  total?: number;
  page?: number;
  page_size?: number;
};

type RequestOptions = RequestInit & {
  token?: string | null;
};

function readBrowserToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(SESSION_TOKEN_KEY);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = options.token === undefined ? readBrowserToken() : options.token;

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: options.cache ?? "no-store"
  });
  const payload = (await response.json().catch(() => ({}))) as Partial<ApiResponse<T>> & {
    error?: { code?: string; message?: string; details?: unknown };
  };

  if (!response.ok || payload.success === false) {
    throw new ApiError(
      payload.error?.message || payload.message || `HTTP ${response.status}`,
      response.status,
      payload.error?.code,
      payload.error?.details
    );
  }

  return payload.data as T;
}

export async function fetchHealth(): Promise<{ status: string; reachable: boolean }> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!response.ok) {
      return { status: `HTTP ${response.status}`, reachable: false };
    }
    const data = (await response.json()) as { status?: string };
    return { status: data.status || "unknown", reachable: data.status === "ok" };
  } catch {
    return { status: "unreachable", reachable: false };
  }
}

const jsonBody = (value: unknown) => JSON.stringify(value);

export function login(uid: string, password: string) {
  return apiRequest<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: jsonBody({ uid, password })
  });
}

export function getCurrentUser() {
  return apiRequest<User>("/api/v1/auth/me");
}

export function listUsers(params: ListUsersParams = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return apiRequest<ListResult<User>>(`/api/v1/users${query ? `?${query}` : ""}`);
}

export function listBusinessUserOptions() {
  return apiRequest<ListResult<BusinessUserOption>>("/api/v1/business-user-options");
}

export function createUser(payload: UserPayload & { uid: string }) {
  return apiRequest<User>("/api/v1/users", { method: "POST", body: jsonBody(payload) });
}

export function updateUser(userId: number, payload: UserPayload) {
  return apiRequest<User>(`/api/v1/users/${userId}`, { method: "PUT", body: jsonBody(payload) });
}

export function updateUserPermissions(userId: number, permissions: string[]) {
  return apiRequest<User>(`/api/v1/users/${userId}/permissions`, {
    method: "PUT",
    body: jsonBody({ permissions })
  });
}

export function enableUser(userId: number) {
  return apiRequest<User>(`/api/v1/users/${userId}/enable`, { method: "POST" });
}

export function disableUser(userId: number) {
  return apiRequest<User>(`/api/v1/users/${userId}/disable`, { method: "POST" });
}

export function deleteUser(userId: number) {
  return apiRequest<User>(`/api/v1/users/${userId}`, { method: "DELETE" });
}

export function getSystemSettings() {
  return apiRequest<Record<string, unknown>>("/api/v1/system-settings");
}

export function saveSystemSetting(key: string, value: unknown) {
  return apiRequest<{ key: string; value: unknown }>(`/api/v1/system-settings/${key}`, {
    method: "PUT",
    body: jsonBody({ value })
  });
}

export function validateVdriveLink(vdrive_url: string) {
  return apiRequest<VDriveValidation>("/api/v1/vdrive/validate-folder-link", {
    method: "POST",
    body: jsonBody({ vdrive_url })
  });
}

export function listProjects(params: ListProjectsParams = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return apiRequest<ListResult<Project>>(`/api/v1/projects${query ? `?${query}` : ""}`);
}

export function listArchiveProjects(params: ListArchiveProjectsParams = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return apiRequest<ListResult<ArchiveProject>>(`/api/v1/archive-projects${query ? `?${query}` : ""}`);
}

export function createProject(payload: Record<string, unknown>) {
  return apiRequest<Project>("/api/v1/projects", { method: "POST", body: jsonBody(payload) });
}

export function getProject(projectId: number) {
  return apiRequest<Project>(`/api/v1/projects/${projectId}`);
}

export function updateProject(projectId: number, payload: Record<string, unknown>) {
  return apiRequest<Project>(`/api/v1/projects/${projectId}`, { method: "PATCH", body: jsonBody(payload) });
}

export function updateProjectVdrive(projectId: number, payload: { vdrive_url: string }) {
  return apiRequest<Project>(`/api/v1/projects/${projectId}/vdrive-link`, { method: "POST", body: jsonBody(payload) });
}

export function addProjectOrder(projectId: number, payload: { receive_date: string; models: string[] }) {
  return apiRequest<{ id: number }>(`/api/v1/projects/${projectId}/orders`, {
    method: "POST",
    body: jsonBody(payload)
  });
}

export function deleteProject(projectId: number, payload: { confirm_project_name: string; delete_reason?: string }) {
  return apiRequest<Project>(`/api/v1/projects/${projectId}`, { method: "DELETE", body: jsonBody(payload) });
}

export function listQGNodes() {
  return apiRequest<ListResult<QGNode>>("/api/v1/qg-nodes");
}

export function listRuleVersions(qgNodeId?: number) {
  const query = qgNodeId ? `?qg_node_id=${qgNodeId}` : "";
  return apiRequest<ListResult<RuleVersion>>(`/api/v1/business-rule-versions${query}`);
}

export function createRuleVersion(payload: { qg_node_id: number; version_no: string; change_summary?: string }) {
  return apiRequest<RuleVersion>("/api/v1/business-rule-versions", { method: "POST", body: jsonBody(payload) });
}

export function prepareEditableRuleVersion(qgNodeId: number) {
  return apiRequest<RuleVersion>(`/api/v1/qg-nodes/${qgNodeId}/editable-rule-version`, { method: "POST" });
}

export function getRuleVersion(versionId: number) {
  return apiRequest<RuleVersion>(`/api/v1/business-rule-versions/${versionId}`);
}

export function createBusinessRule(versionId: number, payload: Record<string, unknown>) {
  return apiRequest<BusinessRule>(`/api/v1/business-rule-versions/${versionId}/business-check-rules`, {
    method: "POST",
    body: jsonBody(payload)
  });
}

export function updateBusinessRule(ruleId: number, payload: Record<string, unknown>) {
  return apiRequest<BusinessRule>(`/api/v1/business-check-rules/${ruleId}`, {
    method: "PATCH",
    body: jsonBody(payload)
  });
}

export function createExecutionRule(ruleId: number, payload: Record<string, unknown>) {
  return apiRequest<AutoCheckExecutionRule>(`/api/v1/business-check-rules/${ruleId}/auto-check-execution-rules`, {
    method: "POST",
    body: jsonBody(payload)
  });
}

export function publishRuleVersion(versionId: number, payload: { change_summary?: string } = {}) {
  return apiRequest<RuleVersion>(`/api/v1/business-rule-versions/${versionId}/publish`, {
    method: "POST",
    body: jsonBody(payload)
  });
}

export function listInspectionTasks() {
  return apiRequest<ListResult<InspectionTask>>("/api/v1/inspection-tasks");
}

export function prepareInspectionTask(vdrive_url: string) {
  return apiRequest<InspectionTaskPrepare>("/api/v1/inspection-tasks/prepare", {
    method: "POST",
    body: jsonBody({ vdrive_url })
  });
}

export function createInspectionTask(payload: Record<string, unknown>) {
  return apiRequest<InspectionTask>("/api/v1/inspection-tasks", { method: "POST", body: jsonBody(payload) });
}

export function getInspectionTask(taskId: number) {
  return apiRequest<InspectionTask>(`/api/v1/inspection-tasks/${taskId}`);
}

export function listCurrentRoundItems(taskId: number) {
  return apiRequest<{ round_id: number; round_no: number; items: InspectionItem[] }>(
    `/api/v1/inspection-tasks/${taskId}/current-round/items`
  );
}

export function getInspectionItem(itemId: number) {
  return apiRequest<InspectionItem>(`/api/v1/inspection-items/${itemId}`);
}

export function convertInspectionItemToManual(itemId: number, reason: string) {
  return apiRequest<InspectionItem>(`/api/v1/inspection-items/${itemId}/convert-to-manual`, {
    method: "POST",
    body: jsonBody({ reason })
  });
}

export function confirmInspectionItem(itemId: number, payload: Record<string, unknown>) {
  return apiRequest<{ item: InspectionItem; decision_id: number }>(`/api/v1/inspection-items/${itemId}/confirm`, {
    method: "POST",
    body: jsonBody(payload)
  });
}

export function archiveCurrentRound(taskId: number) {
  return apiRequest<Record<string, unknown>>(`/api/v1/inspection-tasks/${taskId}/archive-current-round`, {
    method: "POST"
  });
}

export function voidInspectionTask(taskId: number, void_reason: string) {
  return apiRequest<InspectionTask>(`/api/v1/inspection-tasks/${taskId}/void`, {
    method: "POST",
    body: jsonBody({ void_reason })
  });
}

export function listRectifications(taskId?: number) {
  const query = taskId ? `?task_id=${taskId}` : "";
  return apiRequest<ListResult<RectificationItem>>(`/api/v1/rectification-items${query}`);
}

export function markRectificationDone(rectificationId: number) {
  return apiRequest<RectificationItem>(`/api/v1/rectification-items/${rectificationId}/mark-done`, { method: "POST" });
}

export function undoRectificationDone(rectificationId: number) {
  return apiRequest<RectificationItem>(`/api/v1/rectification-items/${rectificationId}/undo-done`, { method: "POST" });
}

export function listFollowups(taskId?: number) {
  const query = taskId ? `?task_id=${taskId}` : "";
  return apiRequest<ListResult<FollowUpItem>>(`/api/v1/followup-items${query}`);
}

export function closeFollowup(followupId: number) {
  return apiRequest<FollowUpItem>(`/api/v1/followup-items/${followupId}/close`, { method: "POST" });
}

export function triggerRecheck(taskId: number) {
  return apiRequest<Record<string, unknown>>(`/api/v1/inspection-tasks/${taskId}/trigger-recheck`, { method: "POST" });
}

export function listReports(params: { project_id?: string; qg_node_id?: string; overall_result?: string } = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return apiRequest<ListResult<Report>>(`/api/v1/reports${query ? `?${query}` : ""}`);
}

export function getReport(reportId: number) {
  return apiRequest<Report>(`/api/v1/reports/${reportId}`);
}

export function getDashboardOverview() {
  return apiRequest<DashboardOverview>("/api/v1/dashboard/overview");
}

export function getDashboardTodos() {
  return apiRequest<ListResult<DashboardTodo>>("/api/v1/dashboard/my-todos");
}
