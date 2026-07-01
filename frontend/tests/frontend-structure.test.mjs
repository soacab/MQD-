import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

describe("frontend structure", () => {
  it("keeps a Next app entry and health API client", () => {
    const page = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");

    assert.match(page, /board-workbench/);
    assert.match(page, /fetchHealth/);
    assert.match(page, /getDashboardOverview/);
    assert.match(page, /getDashboardTodos/);
    for (const snippet of ["进行中", "复查中", "待跟进"]) {
      assert.match(page, new RegExp(snippet), `home page should expose ${snippet}`);
    }
    assert.match(api, /\/health/);
  });

  it("uses one typed API client with bearer auth and P0 endpoints", () => {
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");

    assert.match(api, /export type ApiResponse/);
    assert.match(api, /export class ApiError/);
    assert.match(api, /apiRequest/);
    assert.match(api, /Authorization/);
    assert.match(api, /Bearer/);

    const endpoints = [
      "/api/v1/auth/login",
      "/api/v1/auth/me",
      "/api/v1/users",
      "/api/v1/system-settings",
      "/api/v1/vdrive/validate-folder-link",
      "/api/v1/projects",
      "/api/v1/qg-nodes",
      "/api/v1/qg-nodes/",
      "/api/v1/business-rule-versions",
      "/api/v1/inspection-tasks/prepare",
      "/api/v1/inspection-tasks",
      "/api/v1/rectification-items",
      "/api/v1/followup-items",
      "/api/v1/reports",
      "/api/v1/archive-projects",
      "/api/v1/dashboard/overview",
      "/api/v1/dashboard/my-todos"
    ];

    for (const endpoint of endpoints) {
      assert.match(api, new RegExp(endpoint.replaceAll("/", "\\/")));
    }
  });

  it("keeps session state in a dedicated browser helper", () => {
    const sessionPath = resolve(root, "lib/session.ts");
    assert.equal(existsSync(sessionPath), true, "lib/session.ts should exist");

    const session = readFileSync(sessionPath, "utf8");
    assert.match(session, /localStorage/);
    assert.match(session, /getStoredToken/);
    assert.match(session, /saveSession/);
    assert.match(session, /updateStoredUser/);
    assert.match(session, /clearSession/);
  });

  it("includes P0 workflow pages", () => {
    const pages = [
      "app/login/page.tsx",
      "app/admin/page.tsx",
      "app/projects/page.tsx",
      "app/rules/page.tsx",
      "app/inspection/page.tsx",
      "app/reports/page.tsx",
      "app/rectification/page.tsx"
    ];

    for (const page of pages) {
      assert.equal(existsSync(resolve(root, page)), true, `${page} should exist`);
    }
  });

  it("turns P0 workflow pages into API-backed client pages", () => {
    const pageExpectations = {
      "app/login/page.tsx": ["use client", "login(", "saveSession"],
      "app/admin/page.tsx": [
        "use client",
        "listUsers(",
        "createUser(",
        "updateUser(",
        "deleteUser(",
        "权限管理",
        "只读模式",
        "确认删除 UID",
        "account-body",
        "account-sidebar",
        "account-user-layout",
        "account-table",
        "permission-list",
        "account-modal",
        "activeSection",
        "showUserModal",
        "添加用户",
        "type=\"checkbox\""
      ],
      "app/projects/page.tsx": ["use client", "listProjects(", "updateProject(", "updateProjectVdrive(", "addProjectOrder(", "deleteProject("],
      "app/rules/page.tsx": ["use client", "listQGNodes(", "prepareEditableRuleVersion(", "publishRuleVersion("],
      "app/inspection/page.tsx": ["use client", "confirmInspectionItem(", "archiveCurrentRound("],
      "app/reports/page.tsx": ["use client", "listArchiveProjects(", "listBusinessUserOptions(", "getProject(", "addProjectOrder("],
      "app/rectification/page.tsx": ["use client", "listRectifications(", "triggerRecheck("]
    };

    for (const [page, expectedSnippets] of Object.entries(pageExpectations)) {
      const source = readFileSync(resolve(root, page), "utf8");
      for (const snippet of expectedSnippets) {
        assert.match(source, new RegExp(snippet.replaceAll("(", "\\(")), `${page} should contain ${snippet}`);
      }
    }
  });

  it("exposes account permission administration API helpers", () => {
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");

    for (const snippet of [
      "permission?: string",
      "updateUser(",
      "updateUserPermissions(",
      "enableUser(",
      "disableUser(",
      "deleteUser("
    ]) {
      assert.match(api, new RegExp(snippet.replaceAll("(", "\\(").replaceAll("?", "\\?")), `api should contain ${snippet}`);
    }
  });

  it("guards the current user in account administration UI", () => {
    const adminPage = readFileSync(resolve(root, "app/admin/page.tsx"), "utf8");

    for (const snippet of [
      "updateStoredUser",
      "isEditingCurrentUser",
      "isCurrentUser(item)",
      "不能停用当前登录账号",
      "不能删除当前登录账号",
      "不能取消自己的权限管理权限",
      "disabled={!canManageAccounts || isCurrentUser(item)}",
      "account-readonly-note",
      "account-permission-filter",
      "account-status-filter",
      "account-status-radios"
    ]) {
      assert.match(adminPage, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `admin page should contain ${snippet}`);
    }
  });

  it("supports P0 experience hardening for VDrive, rules, and dashboard", () => {
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");
    const homePage = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const projectsPage = readFileSync(resolve(root, "app/projects/page.tsx"), "utf8");
    const inspectionPage = readFileSync(resolve(root, "app/inspection/page.tsx"), "utf8");
    const newTaskModal = readFileSync(resolve(root, "app/NewTaskModal.tsx"), "utf8");
    const rectificationPage = readFileSync(resolve(root, "app/rectification/page.tsx"), "utf8");
    const rulesPage = readFileSync(resolve(root, "app/rules/page.tsx"), "utf8");

    for (const snippet of [
      "getProject(",
      "listProjects(params",
      "updateProject(",
      "updateProjectVdrive(",
      "listBusinessUserOptions(",
      "updateBusinessRule(",
      "prepareEditableRuleVersion(",
      "getDashboardOverview(",
      "getDashboardTodos("
    ]) {
      assert.match(api, new RegExp(snippet.replaceAll("(", "\\(")), `api should contain ${snippet}`);
    }

    for (const snippet of [
      "prepareInspectionTask(",
      "suggested_project_name",
      "校验链接",
      "下一步：确认信息",
      "开始执行"
    ]) {
      assert.match(newTaskModal, new RegExp(snippet.replaceAll("(", "\\(")), `new task modal should contain ${snippet}`);
    }
    assert.doesNotMatch(inspectionPage, /项目 ID/, "inspection task creation should not ask users for project ID");
    assert.doesNotMatch(newTaskModal, /vdrivePreview/, "new task modal should use the VDrive-first prepare result");

    for (const snippet of ["archiveSummary", "window.confirm", "归档前确认", "归档后可进入报告页查看结论"]) {
      assert.match(inspectionPage, new RegExp(snippet.replaceAll("(", "\\(")), `inspection page should contain ${snippet}`);
    }

    for (const snippet of ["confirmRectificationAction", "confirmRecheckAction", "window.confirm", "复查已触发，可返回点检页执行新轮次"]) {
      assert.match(rectificationPage, new RegExp(snippet.replaceAll("(", "\\(")), `rectification page should contain ${snippet}`);
    }

    for (const snippet of [
      "board-task-card",
      "进入检查",
      "查看任务清单",
      "board-followup-table",
      "markFollowupDone",
      "window.confirm",
      "projectDetailTodo",
      "role=\"dialog\"",
      "rectification_done_count"
    ]) {
      assert.match(homePage, new RegExp(snippet.replaceAll("(", "\\(")), `home page should contain ${snippet}`);
    }

    for (const snippet of ["deleteConfirmName", "手动输入项目名称", "confirm_project_name: deleteConfirmName"]) {
      assert.match(projectsPage, new RegExp(snippet.replaceAll("(", "\\(")), `projects page should contain ${snippet}`);
    }

    for (const snippet of [
      "project_category",
      "project_level",
      "mq_user_id",
      "planned_mp_date",
      "production_line",
      "updateProject(",
      "updateProjectVdrive(",
      "listFilters",
      "status: \"normal\"",
      "接收批次",
      "保存基础信息",
      "更新 VDrive"
    ]) {
      assert.match(projectsPage, new RegExp(snippet.replaceAll("(", "\\(")), `projects page should contain ${snippet}`);
    }

    for (const snippet of [
      "getCurrentUser(",
      "canManageRules",
      "updateBusinessRule(",
      "规则管理员可编辑",
      "只读模式",
      "检查阶段",
      "rules-workspace",
      "rules-node-nav",
      "rules-history-drawer",
      "rules-modal-backdrop",
      "自动检查项",
      "人工检查项",
      "版本历史",
      "发布规则版本"
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(")), `rules page should contain ${snippet}`);
    }

    for (const snippet of [
      "is_apqp",
      "is_active",
      "停用人工检查项",
      "published_by_name",
      "is_current",
      "change_details",
      "draftChangeDetails",
      "确认发布规则版本",
      "当前版本",
      "新增人工检查项",
      "继续编辑未发布规则变更"
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(")), `rules page should contain ${snippet}`);
    }

    for (const forbidden of [
      "检查项编码",
      "排序",
      "createExecutionRule(",
      "await createExecutionRule",
      "{item.rule_code}：",
      "{ruleForm.rule_code}"
    ]) {
      assert.doesNotMatch(rulesPage, new RegExp(forbidden.replaceAll("(", "\\(")), `rules page should not expose ${forbidden}`);
    }

    for (const snippet of [
      "新增人工检查项",
      "检查项名称",
      "Checklist 要求",
      "责任方",
      "APQP",
      "状态",
      "nodeRuleCounts",
      "published_rule_count",
      "draftVersion",
      "canManageRules && draftVersion",
      "继续编辑草稿"
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(")), `rules page should keep ${snippet}`);
    }
    assert.doesNotMatch(rulesPage, /loadNodeRuleCounts/, "rules page should not fetch each node detail just to render sidebar counts");
  });

  it("keeps task creation as the only user-facing creation entry", () => {
    const homePage = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const projectsPage = readFileSync(resolve(root, "app/projects/page.tsx"), "utf8");
    const inspectionPage = readFileSync(resolve(root, "app/inspection/page.tsx"), "utf8");

    assert.doesNotMatch(homePage, /项目创建/, "home page should not advertise project creation");
    assert.match(homePage, /进入检查/, "home page should guide users into inspection tasks");

    assert.doesNotMatch(projectsPage, /createProject\(/, "project archive page should not call project creation from the UI");
    assert.doesNotMatch(projectsPage, /handleCreate/, "project archive page should not keep a create-project submit flow");
    assert.doesNotMatch(projectsPage, /创建项目/, "project archive page should not show create-project copy");
    assert.match(projectsPage, /项目档案维护/, "project page should be framed as archive maintenance");

    const appNav = readFileSync(resolve(root, "app/AppNav.tsx"), "utf8");
    const newTaskModal = readFileSync(resolve(root, "app/NewTaskModal.tsx"), "utf8");

    assert.match(homePage, /NewTaskModal/, "home page should host the task creation modal");
    assert.match(newTaskModal, /新建检查任务/, "new task modal should match prototype task naming");
    assert.match(newTaskModal, /关联项目基础信息|项目基础信息/, "new task modal should frame project fields as linked task context");
    assert.match(newTaskModal, /new-task-modal/, "new task modal should expose modal structure");
    assert.match(newTaskModal, /prepareInspectionTask\(/, "new task modal should prepare VDrive-first creation");
    assert.match(newTaskModal, /createInspectionTask\(/, "new task modal should create tasks through the existing API");
    assert.doesNotMatch(newTaskModal, /常用 VDrive|有历史记录|VDrive\/727D_广丰MLM|VDrive\/NEWPROJECT_SAMPLE/, "new task modal should not bake prototype demo path options into product UI");
    assert.match(appNav, /checkflow:new-task/, "topbar create action should open the workbench modal");
    assert.doesNotMatch(appNav, /href="\/inspection"/, "topbar create action should not navigate to /inspection for creation");
    assert.doesNotMatch(inspectionPage, /wizard-panel/, "inspection execution page should not render the task creation wizard");
    assert.doesNotMatch(inspectionPage, /prepareInspectionTask\(/, "inspection execution page should not own task creation prepare calls");
    assert.match(inspectionPage, /VDrive 扫描、文件内容解析、QMS\/UCM 直连仍为 mock 或未接入真实接口/, "inspection page should disclose external integration limits");
    assert.doesNotMatch(inspectionPage, /<h2>新建检查任务<\/h2>/, "inspection page should not use inconsistent task naming");

    const payloadStart = newTaskModal.indexOf("const task = await createInspectionTask({");
    const payloadEnd = newTaskModal.indexOf("});", payloadStart);
    assert.notEqual(payloadStart, -1, "new task modal should create tasks through createInspectionTask");
    assert.notEqual(payloadEnd, -1, "inspection task payload should be a concrete object");
    const createTaskPayload = newTaskModal.slice(payloadStart, payloadEnd);
    for (const snippet of [
      "project_category: taskForm.project_category",
      "bu: taskForm.bu",
      "project_level: taskForm.project_level",
      "mq_user_id: Number(taskForm.mq_user_id)",
      "mp_owner: taskForm.mp_owner",
      "group_name: taskForm.group_name",
      "production_line: selectedLine"
    ]) {
      assert.match(createTaskPayload, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `task creation payload should contain ${snippet}`);
    }
  });

  it("keeps new task permission visible but disabled without inspection execution permission", () => {
    const appNav = readFileSync(resolve(root, "app/AppNav.tsx"), "utf8");

    for (const snippet of [
      "canCreateTask = Boolean(user?.permissions.includes(\"inspection_engineer\"))",
      "aria-disabled=\"true\"",
      "当前账号没有点检执行权限",
      "app-create-task disabled"
    ]) {
      assert.match(appNav, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)").replaceAll("?", "\\?")), `AppNav should contain ${snippet}`);
    }
    assert.doesNotMatch(appNav, /project_admin"\]/, "project_admin alone should not enable task creation");
    assert.doesNotMatch(appNav, /if \(!user\) \{\s*return true;\s*\}/, "unknown session should not be treated as allowed");
  });

  it("uses one workbench href rule for recheck cards and detail modals", () => {
    const homePage = readFileSync(resolve(root, "app/page.tsx"), "utf8");

    assert.match(homePage, /function todoHref\(todo: DashboardTodo\)/, "home page should centralize dashboard todo href logic");
    assert.match(homePage, /const href = todoHref\(todo\)/, "task cards should use centralized href logic");
    assert.match(homePage, /href=\{todoHref\(projectDetailTodo\)\}/, "detail modal should use the same href logic");
  });

  it("keeps historical task field values selectable when they are outside fixed options", () => {
    const newTaskModal = readFileSync(resolve(root, "app/NewTaskModal.tsx"), "utf8");

    assert.match(newTaskModal, /function optionsWithCurrent/, "new task modal should append historical values to fixed select options");
    for (const snippet of [
      "optionsWithCurrent(customerOptions, taskForm.customer)",
      "optionsWithCurrent(projectCategories, taskForm.project_category)",
      "optionsWithCurrent(buOptions, taskForm.bu)",
      "optionsWithCurrent(projectLevels, taskForm.project_level)",
      "optionsWithCurrent(groupOptions, taskForm.group_name)"
    ]) {
      assert.match(newTaskModal, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `new task modal should contain ${snippet}`);
    }
  });

  it("aligns reports page with the inspection archive project list", () => {
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");
    const reportsPage = readFileSync(resolve(root, "app/reports/page.tsx"), "utf8");
    const styles = readFileSync(resolve(root, "app/styles.css"), "utf8");

    for (const snippet of [
      "export type ArchiveProject",
      "export type ListArchiveProjectsParams",
      "export type BusinessUserOption",
      "listArchiveProjects(",
      "listBusinessUserOptions(",
      "/api/v1/archive-projects",
      "/api/v1/business-user-options",
      "report_last_modified_at",
      "latest_report_id"
    ]) {
      assert.match(api, new RegExp(snippet.replaceAll("(", "\\(")), `api should contain ${snippet}`);
    }

    for (const snippet of [
      "检查档案",
      "archiveFilters",
      "resolveDefaultArchiveFilters",
      "me.id",
      "项目名称或机型",
      "全部QG节点",
      "全部QG结论",
      "选择日期范围",
      "dateRangeLabel",
      "pendingDateFrom",
      "pendingDateTo",
      "calendarMonth",
      "calendarMonths",
      "selectCalendarDate",
      "shiftCalendarMonth",
      "archive-calendar-grid",
      "archive-calendar-day selected",
      "archive-calendar-day in-range",
      "archive-date-trigger",
      "archive-date-popover",
      "重置日期",
      "导出 Excel",
      "项目创建时间",
      "当前QG节点",
      "本轮结论",
      "报告修改时间",
      "项目详情",
      "机型 & 加单记录",
      "handleAddOrder",
      "isAddingOrder",
      "disabled={isAddingOrder}",
      "deleteConfirmName",
      "confirm_project_name: deleteConfirmName",
      "作废/隐藏项目",
      "报告生成时间",
      "最近修改时间",
      "检查项结论进度",
      "过程记录",
      "inspected_at"
    ]) {
      assert.match(reportsPage, new RegExp(snippet.replaceAll("(", "\\(")), `reports page should contain ${snippet}`);
    }

    assert.doesNotMatch(reportsPage, /field-governance-note/, "reports page should not show internal field governance copy");
    assert.doesNotMatch(reportsPage, /删除项目/, "reports page should use void-hide copy instead of delete copy");
    assert.doesNotMatch(reportsPage, /className="archive-date-range"/, "reports page should use one range picker trigger instead of two toolbar date inputs");
    assert.doesNotMatch(reportsPage, /aria-label="报告修改开始日期"/, "reports page should not expose a split start date input in the toolbar");
    assert.doesNotMatch(reportsPage, /aria-label="报告修改结束日期"/, "reports page should not expose a split end date input in the toolbar");

    for (const snippet of [
      ".archive-shell",
      ".archive-toolbar",
      ".archive-table",
      ".archive-result-pill",
      ".archive-modal-backdrop",
      ".archive-date-trigger",
      ".archive-date-popover",
      ".archive-calendar-grid",
      ".archive-calendar-month",
      ".archive-calendar-day",
      ".archive-pagination",
      ".archive-report-summary",
      ".archive-report-item"
    ]) {
      assert.match(styles, new RegExp(snippet.replaceAll(".", "\\.")), `styles should contain ${snippet}`);
    }
  });

  it("guards high-impact modal actions against double submission", () => {
    const rulesPage = readFileSync(resolve(root, "app/rules/page.tsx"), "utf8");
    const reportsPage = readFileSync(resolve(root, "app/reports/page.tsx"), "utf8");

    for (const snippet of [
      "isPublishing",
      "setIsPublishing(true)",
      "setIsPublishing(false)",
      "disabled={isPublishing}",
      "role=\"dialog\"",
      "aria-modal=\"true\""
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `rules page should contain ${snippet}`);
    }

    for (const snippet of [
      "isAddingOrder",
      "setIsAddingOrder(true)",
      "setIsAddingOrder(false)",
      "disabled={isAddingOrder}"
    ]) {
      assert.match(reportsPage, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `reports page should contain ${snippet}`);
    }
  });

  it("records product and design source-of-truth decisions for frontend redesign", () => {
    const product = readFileSync(resolve(root, "../PRODUCT.md"), "utf8");
    const design = readFileSync(resolve(root, "../DESIGN.md"), "utf8");
    const reconciliation = readFileSync(resolve(root, "../docs/frontend-field-reconciliation.md"), "utf8");

    for (const snippet of [
      "Register",
      "product",
      "第四章",
      "CheckFlow_原型.html",
      "接口为实现现状"
    ]) {
      assert.match(product, new RegExp(snippet), `PRODUCT.md should contain ${snippet}`);
    }

    for (const snippet of [
      "Design Tokens",
      "Top Navigation",
      "Status Vocabulary",
      "Field Governance",
      "待确认差异"
    ]) {
      assert.match(design, new RegExp(snippet), `DESIGN.md should contain ${snippet}`);
    }

    for (const snippet of [
      "第四章有但原型没有",
      "原型有但第四章没写",
      "接口/页面有但两者都没有",
      "命名不同但可能同义",
      "不擅自展示"
    ]) {
      assert.match(reconciliation, new RegExp(snippet), `field reconciliation should contain ${snippet}`);
    }
  });

  it("uses the prototype-style product shell across P0 pages", () => {
    const layout = readFileSync(resolve(root, "app/layout.tsx"), "utf8");
    const appNav = readFileSync(resolve(root, "app/AppNav.tsx"), "utf8");
    const styles = readFileSync(resolve(root, "app/styles.css"), "utf8");
    const homePage = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const inspectionPage = readFileSync(resolve(root, "app/inspection/page.tsx"), "utf8");
    const reportsPage = readFileSync(resolve(root, "app/reports/page.tsx"), "utf8");

    for (const snippet of ["AppNav"]) {
      assert.match(layout, new RegExp(snippet), `layout should contain ${snippet}`);
    }
    for (const snippet of ["工作台", "规则配置", "检查档案", "\\+ 新建任务", "getStoredUser", "canCreateTask", "/admin"]) {
      assert.match(appNav, new RegExp(snippet), `AppNav should contain ${snippet}`);
    }
    for (const snippet of ["clearSession", "aria-expanded", "app-account-menu", "后台管理", "退出登录"]) {
      assert.match(appNav, new RegExp(snippet), `AppNav account menu should contain ${snippet}`);
    }
    const navItemsSource = appNav.match(/const navItems = \[[\s\S]*?\];/)?.[0] || "";
    assert.doesNotMatch(navItemsSource, /后台管理/, "prototype-style top nav should not expose backend management as a primary tab");

    for (const snippet of [
      "--cf-bg-base",
      "--cf-primary-700",
      "--cf-status-pass-bg",
      ".app-shell",
      ".app-topbar",
      ".board-workbench",
      ".board-task-card",
      ".board-followup-table",
      ".inspector-workspace",
      ".field-governance-note"
    ]) {
      assert.match(styles, new RegExp(snippet.replaceAll(".", "\\.")), `styles should contain ${snippet}`);
    }

    assert.match(homePage, /board-workbench/, "home page should use a prototype-style board layout");
    assert.doesNotMatch(homePage, /label: "待归档"/, "home page should not create a separate archive-ready workbench section");
    assert.doesNotMatch(homePage, /label: "待整改"/, "home page should fold rectification todos into the recheck section");
    assert.match(inspectionPage, /inspector-workspace/, "inspection page should use a three-panel execution workspace");
    assert.doesNotMatch(reportsPage, /field-governance-note/, "reports page should keep internal field governance out of the archive UI");
  });
});
