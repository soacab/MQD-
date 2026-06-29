import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
});
