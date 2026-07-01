import { expect, test, type Page, type Route } from "@playwright/test";

const token = "e2e-token";
const user = {
  id: 7,
  uid: "UID10001",
  name: "王工",
  email: "wang@example.com",
  status: "active",
  permissions: ["inspection_engineer", "rules_admin", "super_admin"]
};

function apiResponse(data: unknown) {
  return {
    success: true,
    data,
    message: "ok"
  };
}

async function fulfillJson(route: Route, data: unknown) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(data)
  });
}

async function mockDashboardApi(page: Page) {
  await page.route("**/health", async (route) => {
    await fulfillJson(route, { status: "ok" });
  });
  await page.route("**/api/v1/dashboard/overview", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(
      route,
      apiResponse({
        running_count: 1,
        recheck_count: 1,
        rectification_count: 0,
        followup_count: 1,
        archive_ready_count: 0
      })
    );
  });
  await page.route("**/api/v1/dashboard/my-todos", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(
      route,
      apiResponse({
        items: [
          {
            type: "running_task",
            target_id: 101,
            task_id: 101,
            project_id: 11,
            project_name: "MLM 电驱控制器",
            qg_node: "QG2",
            title: "MLM 电驱控制器检查",
            status: "running",
            href: "/inspection?task_id=101",
            summary: "待确认 2 项",
            round_label: "第1轮检查",
            confirmed_count: 3,
            total_count: 5,
            progress_percent: 60,
            mq_user_name: "王工",
            mq_user_uid: "UID10001",
            last_operated_at: "2026-06-30T10:20:00",
            auto_check_status: {
              label: "检查项待确认",
              value: "2 项待处理",
              tone: "pending"
            }
          },
          {
            type: "recheck_task",
            target_id: 202,
            task_id: 202,
            project_id: 12,
            project_name: "BMS 壳体复查",
            qg_node: "QG3",
            title: "BMS 壳体复查",
            status: "recheck",
            href: "/inspection?task_id=202",
            summary: "等待复查",
            round_label: "第2轮检查",
            rectification_done_count: 1,
            rectification_total_count: 2,
            rectification_progress_percent: 50,
            mq_user_name: "李工",
            mq_user_uid: "UID10002",
            last_operated_at: "2026-06-30T11:20:00"
          },
          {
            type: "followup_item",
            target_id: 301,
            task_id: 101,
            project_id: 11,
            project_name: "MLM 电驱控制器",
            qg_node: "QG2",
            title: "上传整改照片",
            status: "open",
            href: "/reports/501",
            summary: "请补充现场照片",
            planned_finish_date: "2026-07-02",
            mq_user_name: "王工",
            mq_user_uid: "UID10001",
            last_operated_at: "2026-06-30T12:20:00"
          }
        ]
      })
    );
  });
}

async function mockLoggedInSession(page: Page) {
  await page.addInitScript(
    ([sessionToken, currentUser]) => {
      window.localStorage.setItem("checkflow_access_token", sessionToken);
      window.localStorage.setItem("checkflow_current_user", JSON.stringify(currentUser));
    },
    [token, user]
  );
}

function selectByFieldText(page: Page, labelText: string, value: string) {
  return page.locator(".new-task-field", { hasText: labelText }).locator("select").selectOption(value);
}

test("local login saves the browser session and opens the workbench", async ({ page }) => {
  await mockDashboardApi(page);
  await page.route("**/api/v1/auth/login", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(await route.request().postDataJSON()).toEqual({ uid: "UID10001", password: "secret" });
    await fulfillJson(
      route,
      apiResponse({
        access_token: token,
        token_type: "bearer",
        expires_in: 3600,
        user
      })
    );
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(route, apiResponse(user));
  });

  await page.goto("/login");
  await page.getByLabel("UID").fill("UID10001");
  await page.getByLabel("密码").fill("secret");
  await page.getByRole("button", { name: "登录进入" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: /王工/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /新建任务/ })).toBeEnabled();
  await expect
    .poll(() => page.evaluate(() => window.localStorage.getItem("checkflow_access_token")))
    .toBe(token);
  await expect
    .poll(() => page.evaluate(() => JSON.parse(window.localStorage.getItem("checkflow_current_user") || "{}").uid))
    .toBe("UID10001");
});

test("workbench renders dashboard todos and closes a follow-up item", async ({ page }) => {
  await mockLoggedInSession(page);
  await mockDashboardApi(page);
  let closeFollowupCalled = false;
  await page.route("**/api/v1/followup-items/301/close", async (route) => {
    closeFollowupCalled = true;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(route, apiResponse({ id: 301, closed_at: "2026-07-01T09:00:00" }));
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: /进行中/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "MLM 电驱控制器" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "BMS 壳体复查" })).toBeVisible();
  await expect(page.getByRole("table", { name: "待跟进项" })).toContainText("上传整改照片");

  await page.getByRole("button", { name: "查看项目详情" }).first().click();
  const detailDialog = page.getByRole("dialog", { name: "MLM 电驱控制器" });
  await expect(detailDialog).toContainText("QG2");
  await expect(detailDialog.getByRole("link", { name: "打开任务" })).toHaveAttribute("href", "/inspection?task_id=101");
  await detailDialog.getByRole("button", { name: "关闭项目详情" }).click();

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("上传整改照片");
    await dialog.accept();
  });
  await page.getByRole("button", { name: "标记落实" }).click();
  await expect(page.getByRole("table", { name: "待跟进项" })).not.toContainText("上传整改照片");
  expect(closeFollowupCalled).toBe(true);
});

test("new task wizard prepares VDrive data, creates a task, and redirects to inspection", async ({ page }) => {
  await mockLoggedInSession(page);
  await mockDashboardApi(page);
  await page.route("**/api/v1/qg-nodes", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(
      route,
      apiResponse({
        items: [
          { id: 1, node_code: "QG1", sort_order: 1, published_rule_count: 8 },
          { id: 2, node_code: "QG2", sort_order: 2, published_rule_count: 12 }
        ]
      })
    );
  });
  await page.route("**/api/v1/business-user-options", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    await fulfillJson(route, apiResponse({ items: [{ id: 7, name: "王工", permissions: ["inspection_engineer"] }] }));
  });
  await page.route("**/api/v1/inspection-tasks/prepare", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    expect(await route.request().postDataJSON()).toEqual({ vdrive_url: "https://vdrive.example.com/folders/abc" });
    await fulfillJson(
      route,
      apiResponse({
        vdrive: {
          valid: true,
          folder_guid: "folder-guid",
          folder_id: 88,
          folder_name: "MLM",
          folder_path: "/MQD/MLM"
        },
        has_history: false,
        project: null,
        suggested_project_name: "MLM 自动建议项目",
        recommended_qg_node: { id: 1, node_code: "QG1", sort_order: 1 }
      })
    );
  });
  await page.route("**/api/v1/inspection-tasks", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    expect(await route.request().postDataJSON()).toMatchObject({
      vdrive_url: "https://vdrive.example.com/folders/abc",
      project_name: "MLM 自动建议项目",
      customer: "丰田",
      project_category: "新车型",
      bu: "SMT",
      project_level: "A级",
      mq_user_id: 7,
      mp_owner: "赵经理",
      group_name: "A组",
      planned_mp_date: "2026-08-10",
      production_line: "L01",
      receive_date: "2026-07-01",
      models: ["NV08126"],
      qg_node_id: 1
    });
    await fulfillJson(
      route,
      apiResponse({
        id: 9001,
        inspection_task_id: 9001,
        project_id: 77,
        qg_node_id: 1,
        status: "running",
        current_round_no: 1
      })
    );
  });

  await page.goto("/");
  await page.getByRole("button", { name: /新建任务/ }).click();
  const wizard = page.getByRole("dialog", { name: "新建检查任务" });
  await expect(wizard).toBeVisible();

  await page.getByLabel(/VDrive 项目链接/).fill("https://vdrive.example.com/folders/abc");
  await page.getByRole("button", { name: "校验链接" }).click();
  await expect(page.getByText("链接可访问 · 无历史记录，请手动填写项目信息")).toBeVisible();

  await expect(page.getByLabel(/项目名称/)).toHaveValue("MLM 自动建议项目");
  await selectByFieldText(page, "客户", "丰田");
  await selectByFieldText(page, "项目类别", "新车型");
  await selectByFieldText(page, "BU", "SMT");
  await selectByFieldText(page, "项目等级", "A级");
  await selectByFieldText(page, "MQ人员", "7");
  await page.getByLabel(/对应 MP/).fill("赵经理");
  await selectByFieldText(page, "小组", "A组");
  await page.getByLabel(/计划量产时间/).fill("2026-08-10");
  await selectByFieldText(page, "生产线体", "L01");
  await page.getByLabel(/项目接收时间/).fill("2026-07-01");
  await page.getByPlaceholder("如 NV08126/093").fill("NV08126");
  await page.getByRole("button", { name: /QG1/ }).click();

  await page.getByRole("button", { name: "下一步：确认信息" }).click();
  await expect(wizard).toContainText("请确认以下信息无误");
  await expect(wizard).toContainText("MLM 自动建议项目");

  await page.getByRole("button", { name: "开始执行" }).click();
  await expect(page).toHaveURL("/inspection?task_id=9001");
});
