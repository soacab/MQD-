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
  listBusinessUserOptions,
  listQGNodes,
  prepareInspectionTask,
  type BusinessUserOption,
  type InspectionItem,
  type InspectionTaskPrepare,
  type InspectionTask,
  type QGNode
} from "@/lib/api";

const resultLabels: Record<string, string> = {
  pass: "满足",
  fail: "不满足",
  conditional: "带条件满足",
  na: "不适用"
};

const emptyTaskForm = {
  vdrive_url: "",
  project_name: "",
  customer: "",
  project_category: "",
  bu: "",
  project_level: "",
  mq_user_id: "",
  mp_owner: "",
  group_name: "",
  planned_mp_date: "",
  production_line: "",
  receive_date: "",
  qg_node_id: ""
};

const projectCategories = ["新项目", "派生项目", "年度改款", "量产变更"];
const buOptions = ["智能座舱", "智能驾驶", "车身电子", "制造质量"];
const projectLevels = ["A", "B", "C"];
const groupOptions = ["MQD", "PT", "TE", "MP"];
const productionLines = ["FA", "SMT", "组装线 1", "组装线 2"];

export default function InspectionPage() {
  const [tasks, setTasks] = useState<InspectionTask[]>([]);
  const [qgNodes, setQgNodes] = useState<QGNode[]>([]);
  const [users, setUsers] = useState<BusinessUserOption[]>([]);
  const [selectedTask, setSelectedTask] = useState<InspectionTask | null>(null);
  const [items, setItems] = useState<InspectionItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<InspectionItem | null>(null);
  const [prepareResult, setPrepareResult] = useState<InspectionTaskPrepare | null>(null);
  const [wizardStep, setWizardStep] = useState<"edit" | "confirm">("edit");
  const [message, setMessage] = useState("");
  const [taskForm, setTaskForm] = useState(emptyTaskForm);
  const [models, setModels] = useState([""]);
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
    void loadTaskOptions();
  }, []);

  async function loadTaskOptions() {
    try {
      const [nodeRows, userRows] = await Promise.all([listQGNodes(), listBusinessUserOptions()]);
      setQgNodes(nodeRows.items);
      setUsers(userRows.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务创建选项加载失败");
    }
  }

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

  async function handlePrepareTask() {
    if (!taskForm.vdrive_url.trim()) {
      setMessage("请先粘贴 VDrive 链接。");
      return;
    }
    try {
      const result = await prepareInspectionTask(taskForm.vdrive_url);
      const history = result.project;
      const latestOrder = history?.orders?.at(-1);
      setPrepareResult(result);
      setTaskForm((current) => ({
        ...current,
        vdrive_url: current.vdrive_url,
        project_name: history?.project_name || result.suggested_project_name || current.project_name,
        customer: history?.customer || "",
        project_category: history?.project_category || "",
        bu: history?.bu || "",
        project_level: history?.project_level || "",
        mq_user_id: history?.mq_user_id ? String(history.mq_user_id) : "",
        mp_owner: history?.mp_owner || "",
        group_name: history?.group_name || "",
        planned_mp_date: history?.planned_mp_date || "",
        production_line: history?.production_line || "",
        receive_date: latestOrder?.receive_date || "",
        qg_node_id: result.recommended_qg_node?.id ? String(result.recommended_qg_node.id) : current.qg_node_id
      }));
      setModels(history?.models?.length ? history.models.map((model) => model.model_name) : [""]);
      setWizardStep("edit");
      setMessage(
        result.has_history
          ? "VDrive 链接校验通过，已回填历史项目信息。"
          : "VDrive 链接校验通过，已用文件夹名填入项目名称。"
      );
    } catch (error) {
      setPrepareResult(null);
      setMessage(error instanceof Error ? error.message : "VDrive 链接校验失败");
    }
  }

  function validateTaskForm() {
    const cleanModels = models.map((item) => item.trim()).filter(Boolean);
    if (!prepareResult) {
      return "请先校验 VDrive 链接。";
    }
    if (!taskForm.project_name || !taskForm.customer || !taskForm.receive_date || !taskForm.qg_node_id) {
      return "请补齐项目名称、客户、项目接收时间和 QG 节点。";
    }
    if (!taskForm.project_category || !taskForm.bu || !taskForm.project_level || !taskForm.mq_user_id || !taskForm.mp_owner || !taskForm.group_name || !taskForm.production_line) {
      return "请补齐关联项目基础信息。";
    }
    if (!cleanModels.length) {
      return "至少填写 1 个机型。";
    }
    return "";
  }

  function handleGoConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = validateTaskForm();
    if (error) {
      setMessage(error);
      return;
    }
    setWizardStep("confirm");
    setMessage("");
  }

  async function handleCreateTask() {
    const error = validateTaskForm();
    if (error) {
      setMessage(error);
      setWizardStep("edit");
      return;
    }
    try {
      const task = await createInspectionTask({
        vdrive_url: taskForm.vdrive_url,
        project_name: taskForm.project_name,
        customer: taskForm.customer,
        project_category: taskForm.project_category,
        bu: taskForm.bu,
        project_level: taskForm.project_level,
        mq_user_id: Number(taskForm.mq_user_id),
        mp_owner: taskForm.mp_owner,
        group_name: taskForm.group_name,
        planned_mp_date: taskForm.planned_mp_date,
        production_line: taskForm.production_line,
        receive_date: taskForm.receive_date,
        models: models.map((item) => item.trim()).filter(Boolean),
        qg_node_id: Number(taskForm.qg_node_id)
      });
      const taskId = task.inspection_task_id || task.id;
      setTaskForm(emptyTaskForm);
      setModels([""]);
      setPrepareResult(null);
      setWizardStep("edit");
      setMessage("点检任务已创建。");
      await refreshTasks();
      if (taskId) {
        await loadTask(taskId);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建任务失败");
    }
  }

  function updateModel(index: number, value: string) {
    setModels((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)));
  }

  function addModel() {
    setModels((current) => [...current, ""]);
  }

  function removeModel(index: number) {
    setModels((current) => (current.length === 1 ? [""] : current.filter((_, itemIndex) => itemIndex !== index)));
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
    const archiveSummary = `归档前确认\n\n任务：${selectedTask.task_no || selectedTask.id}\n当前轮次：${selectedTask.current_round_no}\n检查项：${confirmedCount}/${items.length} 已确认\n\n归档后可进入报告页查看结论，并按结论处理整改或待跟进。`;
    if (!window.confirm(archiveSummary)) {
      return;
    }
    try {
      const result = await archiveCurrentRound(selectedTask.id);
      setMessage(`归档完成，结论：${String(result.overall_result || "")}。归档后可进入报告页查看结论。`);
      await refreshTasks();
      await loadTask(selectedTask.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "归档失败");
    }
  }

  const confirmedCount = items.filter((item) => item.status === "confirmed" || item.status === "inherited").length;
  const canArchive = items.length > 0 && confirmedCount === items.length && selectedTask?.status === "running";
  const selectedQGNode = qgNodes.find((node) => String(node.id) === taskForm.qg_node_id);
  const selectedMqUser = users.find((user) => String(user.id) === taskForm.mq_user_id);
  const cleanModels = models.map((item) => item.trim()).filter(Boolean);

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">点检</p>
        <h1>点检执行</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <p className="notice">
        当前页面已接入本系统任务、检查项、工程师确认、归档和报告接口；VDrive 扫描、文件内容解析、QMS/UCM 直连仍为 mock 或未接入真实接口，不作为真实点检有效性结论。
      </p>
      <section className="summary">
        <div>
          <span>1</span>
          <strong>新建点检任务</strong>
          <p>粘贴 VDrive 链接，确认关联项目基础信息和 QG 节点。</p>
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
        <section className="form-panel wizard-panel">
          <div className="section-heading">
            <div>
              <h2>新建点检任务</h2>
              <p>第 {wizardStep === "edit" ? "1" : "2"} 步 / 共 2 步</p>
            </div>
          </div>
          {wizardStep === "edit" ? (
            <form className="stack" onSubmit={handleGoConfirm}>
              <div className="vdrive-row">
                <label>
                  VDrive 项目根链接 <span className="required">*</span>
                  <input
                    name="vdrive_url"
                    value={taskForm.vdrive_url}
                    onChange={(event) => {
                      setTaskForm({ ...taskForm, vdrive_url: event.target.value });
                      setPrepareResult(null);
                    }}
                    placeholder="粘贴 VDrive 链接"
                    required
                  />
                </label>
                <button className="secondary-button" type="button" onClick={handlePrepareTask}>
                  校验路径
                </button>
              </div>
              {prepareResult ? (
                <p className="notice">
                  已识别：{prepareResult.vdrive.folder_path}；{prepareResult.has_history ? "已找到历史记录" : "未找到历史记录"}
                </p>
              ) : null}
              <div className="form-divider">关联项目基础信息</div>
              <label className="wide-field">
                项目名称 <span className="required">*</span>
                <input name="project_name" value={taskForm.project_name} onChange={(event) => setTaskForm({ ...taskForm, project_name: event.target.value })} required />
              </label>
              <div className="form-grid">
                <label>
                  客户 <span className="required">*</span>
                  <select value={taskForm.customer} onChange={(event) => setTaskForm({ ...taskForm, customer: event.target.value })} required>
                    <option value="">请选择</option>
                    <option value="Customer A">Customer A</option>
                    <option value="Customer B">Customer B</option>
                    <option value="比亚迪">比亚迪</option>
                    <option value="理想">理想</option>
                  </select>
                </label>
                <label>
                  项目类别 <span className="required">*</span>
                  <select value={taskForm.project_category} onChange={(event) => setTaskForm({ ...taskForm, project_category: event.target.value })} required>
                    <option value="">请选择</option>
                    {projectCategories.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  BU <span className="required">*</span>
                  <select value={taskForm.bu} onChange={(event) => setTaskForm({ ...taskForm, bu: event.target.value })} required>
                    <option value="">请选择</option>
                    {buOptions.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  项目等级 <span className="required">*</span>
                  <select value={taskForm.project_level} onChange={(event) => setTaskForm({ ...taskForm, project_level: event.target.value })} required>
                    <option value="">请选择</option>
                    {projectLevels.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  MQ 人员 <span className="required">*</span>
                  <select value={taskForm.mq_user_id} onChange={(event) => setTaskForm({ ...taskForm, mq_user_id: event.target.value })} required>
                    <option value="">请选择</option>
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>{user.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  对应 MP（项目经理） <span className="required">*</span>
                  <input value={taskForm.mp_owner} onChange={(event) => setTaskForm({ ...taskForm, mp_owner: event.target.value })} placeholder="请输入项目经理姓名" required />
                </label>
                <label>
                  小组 <span className="required">*</span>
                  <select value={taskForm.group_name} onChange={(event) => setTaskForm({ ...taskForm, group_name: event.target.value })} required>
                    <option value="">请选择</option>
                    {groupOptions.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  计划量产时间
                  <input type="date" value={taskForm.planned_mp_date} onChange={(event) => setTaskForm({ ...taskForm, planned_mp_date: event.target.value })} />
                </label>
              </div>
              <label>
                生产线体 <span className="required">*</span>
                <select value={taskForm.production_line} onChange={(event) => setTaskForm({ ...taskForm, production_line: event.target.value })} required>
                  <option value="">请选择</option>
                  {productionLines.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                项目接收时间 <span className="required">*</span>
                <input type="date" value={taskForm.receive_date} onChange={(event) => setTaskForm({ ...taskForm, receive_date: event.target.value })} required />
              </label>
              <div className="helper-text">首批机型共用该接收时间，后续批次通过加单补充。</div>
              <div className="form-divider">机型</div>
              {models.map((model, index) => (
                <div className="model-row" key={`model-${index}`}>
                  <input value={model} onChange={(event) => updateModel(index, event.target.value)} placeholder="如 NV08126/093" required={index === 0} />
                  <button className="secondary-button" type="button" onClick={() => removeModel(index)} disabled={models.length === 1}>
                    删除
                  </button>
                </div>
              ))}
              <button className="link-button compact-link" type="button" onClick={addModel}>
                + 新增机型
              </button>
              <div className="form-divider">检查信息</div>
              <label>
                QG 节点 <span className="required">*</span>
                <select value={taskForm.qg_node_id} onChange={(event) => setTaskForm({ ...taskForm, qg_node_id: event.target.value })} required>
                  <option value="">请选择</option>
                  {qgNodes.map((node) => (
                    <option key={node.id} value={node.id}>
                      {node.node_code}
                      {prepareResult?.recommended_qg_node?.id === node.id ? "（推荐）" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <div className="button-row">
                <button type="submit">下一步：确认信息</button>
              </div>
            </form>
          ) : (
            <div className="stack">
              <div className="confirm-grid">
                <p><strong>VDrive：</strong>{prepareResult?.vdrive.folder_path || taskForm.vdrive_url}</p>
                <p><strong>项目名称：</strong>{taskForm.project_name}</p>
                <p><strong>客户：</strong>{taskForm.customer}</p>
                <p><strong>项目类别：</strong>{taskForm.project_category}</p>
                <p><strong>BU：</strong>{taskForm.bu}</p>
                <p><strong>项目等级：</strong>{taskForm.project_level}</p>
                <p><strong>MQ 人员：</strong>{selectedMqUser?.name || taskForm.mq_user_id}</p>
                <p><strong>对应 MP：</strong>{taskForm.mp_owner}</p>
                <p><strong>小组：</strong>{taskForm.group_name}</p>
                <p><strong>计划量产时间：</strong>{taskForm.planned_mp_date || "-"}</p>
                <p><strong>生产线体：</strong>{taskForm.production_line}</p>
                <p><strong>项目接收时间：</strong>{taskForm.receive_date}</p>
                <p><strong>机型：</strong>{cleanModels.join(" / ")}</p>
                <p><strong>QG 节点：</strong>{selectedQGNode?.node_code || taskForm.qg_node_id}</p>
              </div>
              <div className="button-row">
                <button className="secondary-button" type="button" onClick={() => setWizardStep("edit")}>
                  返回修改
                </button>
                <button type="button" onClick={() => void handleCreateTask()}>
                  开始点检
                </button>
              </div>
            </div>
          )}
        </section>
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
            <p className="notice">
              归档前确认：当前轮 {confirmedCount}/{items.length} 项已确认。
            </p>
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
