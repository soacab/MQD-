import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

describe("frontend structure", () => {
  it("keeps a Next app entry and health API client", () => {
    const page = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");

    assert.match(page, /工作台与待办/);
    assert.match(page, /fetchHealth/);
    assert.match(page, /getDashboardOverview/);
    assert.match(page, /getDashboardTodos/);
    for (const snippet of ["进行中", "复查中", "待跟进", "待归档"]) {
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
      "/api/v1/business-rule-versions",
      "/api/v1/inspection-tasks/prepare",
      "/api/v1/inspection-tasks",
      "/api/v1/rectification-items",
      "/api/v1/followup-items",
      "/api/v1/reports",
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
        "admin-layout",
        "admin-nav",
        "用户与权限 / 系统设置",
        "type=\"checkbox\""
      ],
      "app/projects/page.tsx": ["use client", "listProjects(", "createProject(", "validateVdriveLink("],
      "app/rules/page.tsx": ["use client", "listQGNodes(", "createRuleVersion(", "publishRuleVersion("],
      "app/inspection/page.tsx": ["use client", "prepareInspectionTask(", "createInspectionTask(", "confirmInspectionItem(", "archiveCurrentRound("],
      "app/reports/page.tsx": ["use client", "listReports(", "getReport("],
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
      "disabled={!canManageAccounts || isCurrentUser(item)}"
    ]) {
      assert.match(adminPage, new RegExp(snippet.replaceAll("(", "\\(").replaceAll(")", "\\)")), `admin page should contain ${snippet}`);
    }
  });

  it("supports P0 experience hardening for VDrive, rules, and dashboard", () => {
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");
    const homePage = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const projectsPage = readFileSync(resolve(root, "app/projects/page.tsx"), "utf8");
    const inspectionPage = readFileSync(resolve(root, "app/inspection/page.tsx"), "utf8");
    const rectificationPage = readFileSync(resolve(root, "app/rectification/page.tsx"), "utf8");
    const rulesPage = readFileSync(resolve(root, "app/rules/page.tsx"), "utf8");

    for (const snippet of [
      "getProject(",
      "listProjects(params",
      "updateProject(",
      "updateProjectVdrive(",
      "updateBusinessRule(",
      "getDashboardOverview(",
      "getDashboardTodos("
    ]) {
      assert.match(api, new RegExp(snippet.replaceAll("(", "\\(")), `api should contain ${snippet}`);
    }

    for (const snippet of [
      "prepareInspectionTask(",
      "suggested_project_name",
      "校验路径",
      "下一步：确认信息",
      "开始点检"
    ]) {
      assert.match(inspectionPage, new RegExp(snippet.replaceAll("(", "\\(")), `inspection page should contain ${snippet}`);
    }
    assert.doesNotMatch(inspectionPage, /项目 ID/, "inspection task creation should not ask users for project ID");
    assert.doesNotMatch(inspectionPage, /vdrivePreview/, "inspection page should use the VDrive-first prepare result");

    for (const snippet of ["archiveSummary", "window.confirm", "归档前确认", "归档后可进入报告页查看结论"]) {
      assert.match(inspectionPage, new RegExp(snippet.replaceAll("(", "\\(")), `inspection page should contain ${snippet}`);
    }

    for (const snippet of ["confirmRectificationAction", "confirmRecheckAction", "window.confirm", "复查已触发，可返回点检页执行新轮次"]) {
      assert.match(rectificationPage, new RegExp(snippet.replaceAll("(", "\\(")), `rectification page should contain ${snippet}`);
    }

    for (const snippet of ["todoActionLabel", "打开任务", "处理整改", "查看报告", "登录后显示你的待办入口"]) {
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
      "自动检查项",
      "人工检查项",
      "版本历史",
      "发布前确认"
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(")), `rules page should contain ${snippet}`);
    }

    for (const snippet of [
      "is_apqp",
      "sort_order",
      "is_active",
      "停用人工检查项",
      "published_by_name",
      "is_current",
      "change_details",
      "draftChangeDetails",
      "确认发布规则版本",
      "当前版本"
    ]) {
      assert.match(rulesPage, new RegExp(snippet.replaceAll("(", "\\(")), `rules page should contain ${snippet}`);
    }
  });
});
