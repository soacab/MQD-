"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  archiveCurrentRound,
  confirmInspectionItem,
  convertInspectionItemToManual,
  createInspectionTask,
  getInspectionItem,
  getInspectionTask,
  listCurrentRoundItems,
  listInspectionTasks,
  type InspectionItem,
  type InspectionTask
} from "@/lib/api";

const resultLabels: Record<string, string> = {
  pass: "满足",
  fail: "不满足",
  conditional: "带条件满足",
  na: "不适用"
};

export default function InspectionPage() {
  const [tasks, setTasks] = useState<InspectionTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<InspectionTask | null>(null);
  const [items, setItems] = useState<InspectionItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<InspectionItem | null>(null);
  const [message, setMessage] = useState("");
  const [taskForm, setTaskForm] = useState({ project_id: "", qg_node_id: "" });
  const [decisionForm, setDecisionForm] = useState({
    decision_result: "pass",
    decision_text: "工程师人工核查确认满足",
    responsible_owner: "MQD",
    planned_finish_date: "",
    countermeasure: "",
    override_reason: ""
  });

  async function refreshTasks() {
    try {
      const rows = await listInspectionTasks();
      setTasks(rows.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务列表加载失败");
    }
  }

  useEffect(() => {
    void refreshTasks();
  }, []);

  async function loadTask(taskId: number) {
    try {
      const task = await getInspectionTask(taskId);
      const current = await listCurrentRoundItems(taskId);
      setSelectedTask(task);
      setItems(current.items);
      setSelectedItem(current.items[0] || null);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务详情加载失败");
    }
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const task = await createInspectionTask({
        project_id: Number(taskForm.project_id),
        qg_node_id: Number(taskForm.qg_node_id)
      });
      const taskId = task.inspection_task_id || task.id;
      setMessage("点检任务已创建。");
      await refreshTasks();
      if (taskId) {
        await loadTask(taskId);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建任务失败");
    }
  }

  async function handleSelectItem(itemId: number) {
    try {
      setSelectedItem(await getInspectionItem(itemId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "检查项详情加载失败");
    }
  }

  async function handleConvertToManual() {
    if (!selectedItem) {
      return;
    }
    try {
      await convertInspectionItemToManual(selectedItem.id, "工程师在前端转人工确认");
      setMessage("检查项已转人工。");
      if (selectedTask?.id) {
        await loadTask(selectedTask.id);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转人工失败");
    }
  }

  async function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedItem || !selectedTask?.id) {
      return;
    }
    try {
      const payload: Record<string, unknown> = {
        decision_result: decisionForm.decision_result,
        decision_text: decisionForm.decision_text
      };
      if (decisionForm.decision_result === "fail" || decisionForm.decision_result === "conditional") {
        payload.responsible_owner = decisionForm.responsible_owner;
        payload.planned_finish_date = decisionForm.planned_finish_date;
      }
      if (decisionForm.decision_result === "conditional") {
        payload.countermeasure = decisionForm.countermeasure;
      }
      if (decisionForm.override_reason) {
        payload.override_auto_result = true;
        payload.override_reason = decisionForm.override_reason;
      }
      await confirmInspectionItem(selectedItem.id, payload);
      setMessage("检查项已确认。");
      await loadTask(selectedTask.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认失败");
    }
  }

  async function handleArchive() {
    if (!selectedTask?.id) {
      return;
    }
    try {
      const result = await archiveCurrentRound(selectedTask.id);
      setMessage(`归档完成，结论：${String(result.overall_result || "")}`);
      await refreshTasks();
      await loadTask(selectedTask.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "归档失败");
    }
  }

  const confirmedCount = items.filter((item) => item.status === "confirmed" || item.status === "inherited").length;
  const canArchive = items.length > 0 && confirmedCount === items.length && selectedTask?.status === "running";

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">点检</p>
        <h1>点检执行</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <section className="summary">
        <div>
          <span>1</span>
          <strong>创建任务</strong>
          <p>选择 normal 项目和已发布 QG 规则。</p>
        </div>
        <div>
          <span>2</span>
          <strong>确认检查项</strong>
          <p>工程师提交 pass、fail、conditional 或 na。</p>
        </div>
        <div>
          <span>3</span>
          <strong>归档当前轮</strong>
          <p>所有检查项确认后计算节点结论。</p>
        </div>
        <div>
          <span>4</span>
          <strong>查看报告</strong>
          <p>归档后进入报告与整改复查。</p>
        </div>
      </section>
      <section className="two-column">
        <form className="form-panel" onSubmit={handleCreateTask}>
          <h2>新建点检任务</h2>
          <label>
            项目 ID
            <input
              name="project_id"
              value={taskForm.project_id}
              onChange={(event) => setTaskForm({ ...taskForm, project_id: event.target.value })}
              required
            />
          </label>
          <label>
            QG 节点 ID
            <input
              name="qg_node_id"
              value={taskForm.qg_node_id}
              onChange={(event) => setTaskForm({ ...taskForm, qg_node_id: event.target.value })}
              required
            />
          </label>
          <button type="submit">创建任务</button>
        </form>
        <section className="module">
          <h2>任务列表</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>项目</th>
                <th>节点</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => {
                const taskId = task.id || task.inspection_task_id;
                return (
                  <tr key={taskId} onClick={() => taskId && void loadTask(taskId)}>
                    <td>{taskId}</td>
                    <td>{task.project_id}</td>
                    <td>{task.qg_node_id}</td>
                    <td>{task.status}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </section>
      {selectedTask ? (
        <section className="three-column spaced">
          <section className="module">
            <h2>检查项导航</h2>
            <p>
              当前轮：{selectedTask.current_round_no}，进度：{confirmedCount}/{items.length}
            </p>
            <ul className="plain-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button className="link-button" type="button" onClick={() => void handleSelectItem(item.id)}>
                    {item.item_name_snapshot}（{item.status}）
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" disabled={!canArchive} onClick={handleArchive}>
              触发归档
            </button>
          </section>
          <section className="module">
            <h2>检查项详情</h2>
            {selectedItem ? (
              <div className="stack">
                <p>名称：{selectedItem.item_name_snapshot}</p>
                <p>类型：{selectedItem.item_type_snapshot}</p>
                <p>状态：{selectedItem.status}</p>
                <p>要求：{selectedItem.checklist_requirement_snapshot || "无"}</p>
                <p>最终结论：{selectedItem.final_result || "未确认"}</p>
                <button className="secondary-button" type="button" onClick={handleConvertToManual}>
                  转人工
                </button>
              </div>
            ) : (
              <p>请选择检查项。</p>
            )}
          </section>
          <form className="form-panel" onSubmit={handleConfirm}>
            <h2>工程师确认</h2>
            <label>
              最终结论
              <select
                value={decisionForm.decision_result}
                onChange={(event) => setDecisionForm({ ...decisionForm, decision_result: event.target.value })}
              >
                {Object.entries(resultLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              判断说明
              <textarea
                value={decisionForm.decision_text}
                onChange={(event) => setDecisionForm({ ...decisionForm, decision_text: event.target.value })}
                required
              />
            </label>
            <label>
              责任人
              <input
                value={decisionForm.responsible_owner}
                onChange={(event) => setDecisionForm({ ...decisionForm, responsible_owner: event.target.value })}
              />
            </label>
            <label>
              计划完成时间
              <input
                type="date"
                value={decisionForm.planned_finish_date}
                onChange={(event) => setDecisionForm({ ...decisionForm, planned_finish_date: event.target.value })}
              />
            </label>
            <label>
              对策
              <input
                value={decisionForm.countermeasure}
                onChange={(event) => setDecisionForm({ ...decisionForm, countermeasure: event.target.value })}
              />
            </label>
            <label>
              推翻 AI 原因
              <input
                value={decisionForm.override_reason}
                onChange={(event) => setDecisionForm({ ...decisionForm, override_reason: event.target.value })}
              />
            </label>
            <button type="submit" disabled={!selectedItem || selectedItem.status === "confirmed"}>
              确认提交
            </button>
          </form>
        </section>
      ) : null}
    </main>
  );
}
