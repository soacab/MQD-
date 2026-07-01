"use client";

import { useEffect, useMemo, useState } from "react";
import {
  closeFollowup,
  fetchHealth,
  getDashboardOverview,
  getDashboardTodos,
  type DashboardOverview,
  type DashboardTodo
} from "@/lib/api";
import { NewTaskModal } from "./NewTaskModal";

const defaultOverview: DashboardOverview = {
  running_count: 0,
  recheck_count: 0,
  rectification_count: 0,
  followup_count: 0,
  archive_ready_count: 0
};

function todoKey(todo: DashboardTodo) {
  return `${todo.type}-${todo.target_id}`;
}

function formatTime(value?: string) {
  if (!value) {
    return "暂无记录";
  }
  return value.replace("T", " ").slice(0, 16);
}

function ownerName(todo: DashboardTodo) {
  if (todo.mq_user_name) {
    return todo.mq_user_name;
  }
  const owner = todo.summary?.split("：")[1];
  return owner || "未分配";
}

function ownerUid(todo: DashboardTodo) {
  return todo.mq_user_uid || "UID未记录";
}

function ownerInitial(todo: DashboardTodo) {
  return ownerName(todo).slice(0, 1);
}

function progressValue(todo: DashboardTodo, compact = false) {
  const confirmed = compact && todo.rectification_done_count !== undefined ? todo.rectification_done_count : todo.confirmed_count ?? 0;
  const total = compact && todo.rectification_total_count !== undefined ? todo.rectification_total_count : todo.total_count ?? 0;
  const explicitPercent = compact && todo.rectification_progress_percent !== undefined ? todo.rectification_progress_percent : todo.progress_percent;
  const percent = explicitPercent ?? (total ? Math.round((confirmed / total) * 100) : 0);
  return {
    confirmed,
    total,
    percent: Math.max(0, Math.min(100, percent))
  };
}

function cardTone(todo: DashboardTodo) {
  if (todo.type === "archive_ready") {
    return "status-pass";
  }
  if (todo.type === "recheck_task" || todo.type === "rectification_item") {
    return "status-review";
  }
  const tone = todo.auto_check_status?.tone;
  if (tone === "pass") {
    return "status-pass";
  }
  if (tone === "fail") {
    return "status-fail";
  }
  if (tone === "pending") {
    return "status-review";
  }
  return "status-running";
}

function autoStatus(todo: DashboardTodo) {
  if (todo.type === "archive_ready") {
    return { label: "检查项待归档", value: "全部已确认", tone: "pass" };
  }
  if (todo.type === "recheck_task" || todo.type === "rectification_item") {
    return { label: "整改复查中", value: todo.summary || "等待复查", tone: "pending" };
  }
  return todo.auto_check_status || { label: "检查项待确认", value: todo.summary || "等待处理", tone: "info" };
}

function dueLabel(date?: string) {
  if (!date) {
    return "";
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(`${date}T00:00:00`);
  if (Number.isNaN(due.getTime())) {
    return "";
  }
  if (due.getTime() < today.getTime()) {
    return "已超期";
  }
  if (due.getTime() === today.getTime()) {
    return "今日到期";
  }
  return "";
}

function todoHref(todo: DashboardTodo) {
  if (todo.type === "recheck_task" || todo.type === "rectification_item") {
    return `/rectification?task_id=${todo.task_id || ""}`;
  }
  return todo.href;
}

function TaskCard({ todo, compact = false, onShowDetail }: { todo: DashboardTodo; compact?: boolean; onShowDetail: (todo: DashboardTodo) => void }) {
  const progress = progressValue(todo, compact);
  const status = autoStatus(todo);
  const actionLabel = todo.type === "recheck_task" || todo.type === "rectification_item" ? "查看任务清单" : "进入检查";
  const href = todoHref(todo);

  return (
    <article className={`board-task-card ${compact ? "board-task-card-sm" : ""} ${cardTone(todo)}`}>
      <div className="board-task-card-head">
        <h3>{todo.project_name || todo.title || `任务 ${todo.task_id || todo.target_id}`}</h3>
        <button className="board-info-button" type="button" onClick={() => onShowDetail(todo)} aria-label="查看项目详情">
          i
        </button>
      </div>
      <div className="board-card-meta">
        <span className="node-tag">{todo.qg_node || "QG待定"}</span>
        <span className="task-card-stage">{todo.round_label || "第1轮检查"}</span>
      </div>
      <div className="task-owner-line">
        <span>MQ人员</span>
        <span className="task-owner-chip">
          <span className="board-avatar">{ownerInitial(todo)}</span>
          {ownerName(todo)} / {ownerUid(todo)}
        </span>
      </div>
      <div className="task-status-stack">
        <div className="task-status-line">
          <span className={`task-status-label ${status.tone}`}>
            <span className="status-mark" aria-hidden="true" />
            <span>{status.label}</span>
          </span>
          <span className={`task-status-value ${status.tone}`}>{status.value}</span>
        </div>
        <div className="task-status-line">
          <span className="task-status-label">{compact ? "整改进度" : "检查项进度"}</span>
          <span className="task-status-value">
            {progress.total ? `${compact ? "" : "已确认 "}${progress.confirmed} / ${progress.total}` : todo.summary || "待处理"}
          </span>
        </div>
        <div className="task-confirm-bar" aria-hidden="true">
          <div className="task-confirm-fill" style={{ width: `${progress.percent}%` }} />
        </div>
      </div>
      <div className="task-time">上次操作 · {formatTime(todo.last_operated_at)}</div>
      <a className={compact ? "board-secondary-action" : "board-primary-action"} href={href}>
        {actionLabel}
      </a>
    </article>
  );
}

export default function Page() {
  const [health, setHealth] = useState({ status: "loading", reachable: false });
  const [overview, setOverview] = useState<DashboardOverview>(defaultOverview);
  const [todos, setTodos] = useState<DashboardTodo[]>([]);
  const [dataError, setDataError] = useState("");
  const [projectDetailTodo, setProjectDetailTodo] = useState<DashboardTodo | null>(null);
  const [newTaskOpen, setNewTaskOpen] = useState(false);

  async function loadDashboard() {
    const healthResult = await fetchHealth();
    setHealth(healthResult);
    try {
      const [overviewResult, todoResult] = await Promise.all([getDashboardOverview(), getDashboardTodos()]);
      setOverview(overviewResult);
      setTodos(todoResult.items);
      setDataError("");
    } catch {
      setOverview(defaultOverview);
      setTodos([]);
      setDataError("待办数据暂不可用");
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  useEffect(() => {
    function openNewTaskModal() {
      setNewTaskOpen(true);
    }
    window.addEventListener("checkflow:new-task", openNewTaskModal);
    if (window.location.search.includes("new_task=1")) {
      setNewTaskOpen(true);
      window.history.replaceState({}, "", window.location.pathname);
    }
    return () => window.removeEventListener("checkflow:new-task", openNewTaskModal);
  }, []);

  const ongoingTodos = useMemo(() => todos.filter((todo) => todo.type === "running_task" || todo.type === "archive_ready"), [todos]);
  const recheckTodos = useMemo(() => todos.filter((todo) => todo.type === "recheck_task" || todo.type === "rectification_item"), [todos]);
  const followupTodos = useMemo(() => todos.filter((todo) => todo.type === "followup_item"), [todos]);

  async function markFollowupDone(todo: DashboardTodo) {
    if (!window.confirm(`确认将「${todo.title || "该待跟进项"}」标记为已落实？`)) {
      return;
    }
    try {
      await closeFollowup(todo.target_id);
      setTodos((current) => current.filter((item) => todoKey(item) !== todoKey(todo)));
      setOverview((current) => ({ ...current, followup_count: Math.max(0, current.followup_count - 1) }));
    } catch {
      setDataError("待跟进项暂无法标记落实");
    }
  }

  return (
    <main className="board-workbench" aria-label="CheckFlow 工作台">
      <div className="board-system-strip">
        <span className={health.reachable ? "board-system-dot ok" : "board-system-dot warn"} aria-hidden="true" />
        <span>{health.reachable ? "后端服务正常" : "后端服务暂不可用"}</span>
        {dataError ? <strong>{dataError}</strong> : null}
      </div>

      <section className="board-group" aria-labelledby="ongoing-title">
        <h2 id="ongoing-title" className="board-group-title">
          <span className="group-dot blue" aria-hidden="true" />
          <span>进行中</span>
          <span className="board-count">{ongoingTodos.length || overview.running_count}</span>
        </h2>
        {ongoingTodos.length ? (
          <div className="board-card-row">
            {ongoingTodos.map((todo) => (
              <TaskCard todo={todo} onShowDetail={setProjectDetailTodo} key={todoKey(todo)} />
            ))}
          </div>
        ) : (
          <div className="board-empty">当前没有进行中的检查任务</div>
        )}
      </section>

      <section className="board-group" aria-labelledby="recheck-title">
        <h2 id="recheck-title" className="board-group-title">
          <span className="group-dot yellow" aria-hidden="true" />
          <span>复查中</span>
          <span className="board-count">{recheckTodos.length || overview.recheck_count + overview.rectification_count}</span>
        </h2>
        {recheckTodos.length ? (
          <div className="board-card-row compact">
            {recheckTodos.map((todo) => (
              <TaskCard todo={todo} compact onShowDetail={setProjectDetailTodo} key={todoKey(todo)} />
            ))}
          </div>
        ) : (
          <div className="board-empty">当前没有待再次检查的任务</div>
        )}
      </section>

      <section className="board-group" aria-labelledby="followup-title">
        <h2 id="followup-title" className="board-group-title">
          <span className="group-dot purple" aria-hidden="true" />
          <span>待跟进</span>
          <span className="board-count">{followupTodos.length || overview.followup_count}</span>
        </h2>
        <div className="board-followup-table" role="table" aria-label="待跟进项">
          <div className="board-followup-head" role="row">
            <span role="columnheader">检查项名称</span>
            <span role="columnheader">项目</span>
            <span role="columnheader">报告节点</span>
            <span role="columnheader">MQ人员</span>
            <span role="columnheader">计划完成时间</span>
            <span role="columnheader">操作</span>
          </div>
          {followupTodos.length ? (
            followupTodos.map((todo) => {
              const deadlineLabel = dueLabel(todo.planned_finish_date);
              return (
                <div className="board-followup-row" role="row" key={todoKey(todo)}>
                  <div role="cell">
                    <strong>{todo.title || `待跟进项 ${todo.target_id}`}</strong>
                    <span>{todo.summary || "请跟进对策落实情况"}</span>
                  </div>
                  <span role="cell">{todo.project_name || `项目 ${todo.project_id || "-"}`}</span>
                  <span role="cell">
                    <span className="board-followup-source">{todo.qg_node || "报告节点待定"}</span>
                  </span>
                  <span role="cell" className="board-followup-owner">
                    <span className="board-avatar">{ownerInitial(todo)}</span>
                    {ownerName(todo)} / {ownerUid(todo)}
                  </span>
                  <span role="cell" className={deadlineLabel ? "deadline urgent" : "deadline"}>
                    {todo.planned_finish_date || "未设置"}
                    {deadlineLabel ? <small>{deadlineLabel}</small> : null}
                  </span>
                  <span role="cell">
                    <button className="board-followup-action" type="button" onClick={() => void markFollowupDone(todo)}>
                      标记落实
                    </button>
                  </span>
                </div>
              );
            })
          ) : (
            <div className="board-followup-empty">当前没有待跟进项</div>
          )}
        </div>
      </section>

      {projectDetailTodo ? (
        <div className="board-modal-backdrop" role="presentation" onClick={() => setProjectDetailTodo(null)}>
          <section className="board-detail-modal" role="dialog" aria-modal="true" aria-labelledby="board-detail-title" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <p className="eyebrow">项目详情</p>
                <h2 id="board-detail-title">{projectDetailTodo.project_name || projectDetailTodo.title || "任务详情"}</h2>
              </div>
              <button type="button" className="board-modal-close" onClick={() => setProjectDetailTodo(null)} aria-label="关闭项目详情">
                ×
              </button>
            </header>
            <div className="board-detail-grid">
              <p>
                <span>QG节点</span>
                <strong>{projectDetailTodo.qg_node || "待定"}</strong>
              </p>
              <p>
                <span>检查轮次</span>
                <strong>{projectDetailTodo.round_label || "第1轮检查"}</strong>
              </p>
              <p>
                <span>MQ人员</span>
                <strong>
                  {ownerName(projectDetailTodo)} / {ownerUid(projectDetailTodo)}
                </strong>
              </p>
              <p>
                <span>上次操作</span>
                <strong>{formatTime(projectDetailTodo.last_operated_at)}</strong>
              </p>
              <p>
                <span>任务状态</span>
                <strong>{projectDetailTodo.status || "待处理"}</strong>
              </p>
              <p>
                <span>任务编号</span>
                <strong>{projectDetailTodo.task_id || projectDetailTodo.target_id}</strong>
              </p>
            </div>
            <footer>
              <a className="board-primary-action" href={todoHref(projectDetailTodo)}>
                打开任务
              </a>
            </footer>
          </section>
        </div>
      ) : null}
      <NewTaskModal open={newTaskOpen} onClose={() => setNewTaskOpen(false)} onCreated={loadDashboard} />
    </main>
  );
}
