import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

describe("frontend structure", () => {
  it("keeps a Next app entry and health API client", () => {
    const page = readFileSync(resolve(root, "app/page.tsx"), "utf8");
    const api = readFileSync(resolve(root, "lib/api.ts"), "utf8");

    assert.match(page, /P0 主流程工作台/);
    assert.match(page, /fetchHealth/);
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
      "/api/v1/inspection-tasks",
      "/api/v1/rectification-items",
      "/api/v1/followup-items",
      "/api/v1/reports"
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
      "app/admin/page.tsx": ["use client", "listUsers(", "createUser(", "saveSystemSetting("],
      "app/projects/page.tsx": ["use client", "listProjects(", "createProject(", "validateVdriveLink("],
      "app/rules/page.tsx": ["use client", "listQGNodes(", "createRuleVersion(", "publishRuleVersion("],
      "app/inspection/page.tsx": ["use client", "createInspectionTask(", "confirmInspectionItem(", "archiveCurrentRound("],
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
});
