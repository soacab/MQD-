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
});
