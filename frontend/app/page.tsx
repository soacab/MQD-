"use client";

import { useEffect, useState } from "react";
import { fetchHealth, getDashboardOverview, getDashboardTodos, type DashboardOverview, type DashboardTodo } from "@/lib/api";

const modules = [
  ["项目档案", "历史项目基础信息、加单、软删除", "/projects"],
  ["规则", "QG 节点、规则版本、检查项、执行规则发布", "/rules"],
  ["点检", "新建点检任务、规则快照、首轮检查项、工程师确认", "/inspection"],
  ["报告", "FULL_GO / C_GO / NO_GO 结论、报告和过程记录", "/reports"],
  ["整改", "整改项、待跟进项、复查轮次", "/rectification"],
  ["后台", "账号权限、系统设置、审计日志", "/admin"]
];

const defaultOverview: DashboardOverview = {
  running_count: 0,
  recheck_count: 0,
  rectification_count: 0,
  followup_count: 0,
  archive_ready_count: 0
};

const todoSections = [
  { key: "running_task", label: "进行中" },
  { key: "recheck_task", label: "复查中" },
  { key: "rectification_item", label: "待整改" },
  { key: "followup_item", label: "待跟进" },
  { key: "archive_ready", label: "待归档" }
];

function todoActionLabel(todo: DashboardTodo) {
  if (todo.type === "rectification_item" || todo.type === "followup_item") {
    return "处理整改";
  }
  if (todo.type === "archive_ready" || todo.type === "running_task" || todo.type === "recheck_task") {
    return "打开任务";
  }
  return "查看报告";
}

export default function Page() {
  const [health, setHealth] = useState({ status: "loading", reachable: false });
  const [overview, setOverview] = useState<DashboardOverview>(defaultOverview);
  const [todos, setTodos] = useState<DashboardTodo[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      const healthResult = await fetchHealth();
      setHealth(healthResult);
      try {
        const [overviewResult, todoResult] = await Promise.all([getDashboardOverview(), getDashboardTodos()]);
        setOverview(overviewResult);
        setTodos(todoResult.items);
        setMessage("");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "登录后显示你的待办入口。");
      }
    }
    void loadDashboard();
  }, []);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">MQD 点检</p>
          <h1>CheckFlow</h1>
        </div>
        <nav aria-label="主导航">
          <a href="/login">登录</a>
          {modules.map(([title, , href]) => (
            <a key={title} href={href}>
              {title}
            </a>
          ))}
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">工作台与待办</p>
            <h2>当前任务入口</h2>
          </div>
          <div className={health.reachable ? "status ok" : "status warn"}>后端 /health: {health.status}</div>
        </header>

        {message ? <p className="notice">{message}</p> : <p className="notice">登录后显示你的待办入口，可直接打开任务、处理整改或查看报告。</p>}

        <section className="summary">
          <div>
            <span>{overview.running_count}</span>
            <strong>进行中</strong>
            <p>正在执行的点检任务。</p>
          </div>
          <div>
            <span>{overview.recheck_count}</span>
            <strong>复查中</strong>
            <p>整改完成后等待复查的任务。</p>
          </div>
          <div>
            <span>{overview.followup_count}</span>
            <strong>待跟进</strong>
            <p>C-GO 后需要关闭的跟进项。</p>
          </div>
          <div>
            <span>{overview.archive_ready_count}</span>
            <strong>待归档</strong>
            <p>检查项已确认，可归档当前轮。</p>
          </div>
        </section>

        <section className="dashboard-grid">
          {todoSections.map((section) => {
            const sectionTodos = todos.filter((todo) => todo.type === section.key);
            return (
              <section className="module" key={section.key}>
                <h3>{section.label}</h3>
                {sectionTodos.length ? (
                  <ul className="plain-list">
                    {sectionTodos.map((todo) => (
                      <li key={`${todo.type}-${todo.target_id}`}>
                        <a className="module-link" href={todo.href}>
                          {todoActionLabel(todo)}：{todo.title || todo.project_name || `任务 ${todo.task_id || todo.target_id}`}
                        </a>
                        <p>{todo.summary || todo.status}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>暂无待办。</p>
                )}
              </section>
            );
          })}
        </section>

        <section className="grid spaced" aria-label="模块入口">
          {modules.map(([title, description, href]) => (
            <article id={title} key={title} className="module">
              <h3>{title}</h3>
              <p>{description}</p>
              <a className="module-link" href={href}>
                进入
              </a>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
