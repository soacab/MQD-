"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createInspectionTask,
  listBusinessUserOptions,
  listQGNodes,
  prepareInspectionTask,
  type BusinessUserOption,
  type InspectionTaskPrepare,
  type QGNode
} from "@/lib/api";

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

const customerOptions = ["丰田", "大众", "宝马", "比亚迪", "理想", "长城"];
const projectCategories = ["新车型", "改款", "平台延伸"];
const buOptions = ["SMT", "ICT", "FA"];
const projectLevels = ["A级", "B级", "C级"];
const groupOptions = ["A组", "B组", "C组"];
const productionLines = ["L01", "L03", "KD-L02", "AH-L04", "AP32-KD", "+ 新增线体"];

function optionsWithCurrent(options: string[], current: string) {
  const cleanCurrent = current.trim();
  if (!cleanCurrent || options.includes(cleanCurrent)) {
    return options;
  }
  return [...options, cleanCurrent];
}

type NewTaskModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated: () => void | Promise<void>;
};

export function NewTaskModal({ open, onClose, onCreated }: NewTaskModalProps) {
  const [qgNodes, setQgNodes] = useState<QGNode[]>([]);
  const [users, setUsers] = useState<BusinessUserOption[]>([]);
  const [taskForm, setTaskForm] = useState(emptyTaskForm);
  const [models, setModels] = useState([""]);
  const [prepareResult, setPrepareResult] = useState<InspectionTaskPrepare | null>(null);
  const [wizardStep, setWizardStep] = useState<"edit" | "confirm">("edit");
  const [pathState, setPathState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [optionMessage, setOptionMessage] = useState("");
  const [customLine, setCustomLine] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    async function loadOptions() {
      try {
        const [nodeRows, userRows] = await Promise.all([listQGNodes(), listBusinessUserOptions()]);
        setQgNodes(nodeRows.items);
        setUsers(userRows.items);
        setOptionMessage("");
      } catch (error) {
        setOptionMessage(error instanceof ApiError && error.status === 401 ? "请先登录后再新建任务。" : "任务创建选项加载失败，请确认后端服务已启动。");
      }
    }
    void loadOptions();
  }, [open]);

  useEffect(() => {
    if (!open) {
      resetForm();
    }
  }, [open]);

  const cleanModels = useMemo(() => models.map((item) => item.trim()).filter(Boolean), [models]);
  const selectedQGNode = qgNodes.find((node) => String(node.id) === taskForm.qg_node_id);
  const selectedMqUser = users.find((user) => String(user.id) === taskForm.mq_user_id);
  const selectedLine = taskForm.production_line === "+ 新增线体" ? customLine.trim() : taskForm.production_line;

  const isStepReady = Boolean(
    prepareResult &&
      taskForm.project_name &&
      taskForm.customer &&
      taskForm.project_category &&
      taskForm.bu &&
      taskForm.project_level &&
      taskForm.mq_user_id &&
      taskForm.mp_owner &&
      taskForm.group_name &&
      taskForm.planned_mp_date &&
      selectedLine &&
      taskForm.receive_date &&
      cleanModels.length &&
      taskForm.qg_node_id
  );

  function resetForm() {
    setTaskForm(emptyTaskForm);
    setModels([""]);
    setPrepareResult(null);
    setWizardStep("edit");
    setPathState("idle");
    setMessage("");
    setOptionMessage("");
    setCustomLine("");
    setIsSubmitting(false);
  }

  function closeModal() {
    resetForm();
    onClose();
  }

  function updateForm(field: keyof typeof emptyTaskForm, value: string) {
    setTaskForm((current) => ({ ...current, [field]: value }));
  }

  function updateVDriveUrl(value: string) {
    setTaskForm((current) => ({ ...current, vdrive_url: value }));
    setPrepareResult(null);
    setPathState("idle");
    setMessage("");
  }

  async function handlePrepareTask() {
    if (!taskForm.vdrive_url.trim()) {
      setMessage("请先粘贴 VDrive 链接。");
      setPathState("error");
      return;
    }
    setPathState("loading");
    setMessage("正在验证链接可访问性...");
    try {
      const result = await prepareInspectionTask(taskForm.vdrive_url);
      const history = result.project;
      const latestOrder = history?.orders?.at(-1);
      const nextLine = history?.production_line || "";
      setPrepareResult(result);
      setTaskForm((current) => ({
        ...current,
        project_name: history?.project_name || result.suggested_project_name || current.project_name,
        customer: history?.customer || "",
        project_category: history?.project_category || "",
        bu: history?.bu || "",
        project_level: history?.project_level || "",
        mq_user_id: history?.mq_user_id ? String(history.mq_user_id) : "",
        mp_owner: history?.mp_owner || "",
        group_name: history?.group_name || "",
        planned_mp_date: history?.planned_mp_date || "",
        production_line: productionLines.includes(nextLine) ? nextLine : nextLine ? "+ 新增线体" : "",
        receive_date: latestOrder?.receive_date || "",
        qg_node_id: result.recommended_qg_node?.id ? String(result.recommended_qg_node.id) : current.qg_node_id
      }));
      setCustomLine(productionLines.includes(nextLine) ? "" : nextLine);
      setModels(history?.models?.length ? history.models.map((model) => model.model_name) : [""]);
      setWizardStep("edit");
      setPathState("success");
      setMessage(result.has_history ? "链接可访问 · 找到历史记录，已自动回填项目信息" : "链接可访问 · 无历史记录，请手动填写项目信息");
    } catch (error) {
      setPrepareResult(null);
      setPathState("error");
      setMessage(error instanceof Error ? error.message : "链接错误或权限不足，请检查后重试");
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

  function handleGoConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isStepReady) {
      setMessage("请先完成路径校验，并补齐所有必填信息。");
      return;
    }
    setMessage("");
    setWizardStep("confirm");
  }

  async function handleCreateTask() {
    if (!isStepReady || isSubmitting) {
      return;
    }
    setIsSubmitting(true);
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
        production_line: selectedLine,
        receive_date: taskForm.receive_date,
        models: cleanModels,
        qg_node_id: Number(taskForm.qg_node_id)
      });
      await onCreated();
      const taskId = task.inspection_task_id || task.id;
      closeModal();
      if (taskId) {
        window.location.href = `/inspection?task_id=${taskId}`;
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建任务失败");
      setIsSubmitting(false);
    }
  }

  if (!open) {
    return null;
  }

  return (
    <div className="new-task-modal-backdrop" role="presentation" onClick={closeModal}>
      <section className="new-task-modal" role="dialog" aria-modal="true" aria-labelledby="new-task-modal-title" onClick={(event) => event.stopPropagation()}>
        <header className="new-task-modal-header">
          <div>
            <h2 id="new-task-modal-title">新建检查任务</h2>
            <div className="new-task-stepper" aria-label={`第 ${wizardStep === "edit" ? "1" : "2"} 步 / 共 2 步`}>
              <span className="active" />
              <span className={wizardStep === "confirm" ? "active" : ""} />
              <strong>第 {wizardStep === "edit" ? "1" : "2"} 步 / 共 2 步</strong>
            </div>
          </div>
          <button type="button" className="new-task-close" onClick={closeModal} aria-label="关闭新建任务">
            ×
          </button>
        </header>

        {wizardStep === "edit" ? (
          <form onSubmit={handleGoConfirm}>
            <div className="new-task-modal-body">
              {optionMessage ? <p className="new-task-option-hint">{optionMessage}</p> : null}
              <div className="new-task-field">
                <label htmlFor="new-task-vdrive">VDrive 项目链接 <span className="required">*</span></label>
                <div className="new-task-path-row">
                  <input
                    id="new-task-vdrive"
                    value={taskForm.vdrive_url}
                    onChange={(event) => updateVDriveUrl(event.target.value)}
                    placeholder="粘贴 VDrive https 链接"
                    required
                  />
                  <button className="new-task-secondary-button" type="button" onClick={() => void handlePrepareTask()}>
                    校验链接
                  </button>
                </div>
                {message ? <p className={`new-task-path-hint ${pathState}`}>{message}</p> : null}
              </div>

              <div className="new-task-section-title">项目基础信息</div>
              <div className="new-task-field">
                <label htmlFor="new-task-project-name">项目名称 <span className="required">*</span></label>
                <input id="new-task-project-name" value={taskForm.project_name} onChange={(event) => updateForm("project_name", event.target.value)} placeholder="请输入项目名称" required />
              </div>

              <div className="new-task-grid-2">
                <SelectField label="客户" value={taskForm.customer} onChange={(value) => updateForm("customer", value)} options={optionsWithCurrent(customerOptions, taskForm.customer)} />
                <SelectField label="项目类别" value={taskForm.project_category} onChange={(value) => updateForm("project_category", value)} options={optionsWithCurrent(projectCategories, taskForm.project_category)} />
                <SelectField label="BU" value={taskForm.bu} onChange={(value) => updateForm("bu", value)} options={optionsWithCurrent(buOptions, taskForm.bu)} />
                <SelectField label="项目等级" value={taskForm.project_level} onChange={(value) => updateForm("project_level", value)} options={optionsWithCurrent(projectLevels, taskForm.project_level)} />
                <SelectField label="MQ人员" value={taskForm.mq_user_id} onChange={(value) => updateForm("mq_user_id", value)} options={users.map((user) => ({ label: user.name, value: String(user.id) }))} />
                <div className="new-task-field">
                  <label htmlFor="new-task-mp-owner">对应 MP（项目经理） <span className="required">*</span></label>
                  <input id="new-task-mp-owner" value={taskForm.mp_owner} onChange={(event) => updateForm("mp_owner", event.target.value)} placeholder="请输入项目经理姓名" required />
                </div>
                <SelectField label="小组" value={taskForm.group_name} onChange={(value) => updateForm("group_name", value)} options={optionsWithCurrent(groupOptions, taskForm.group_name)} />
                <div className="new-task-field">
                  <label htmlFor="new-task-mp-date">计划量产时间 <span className="required">*</span></label>
                  <input id="new-task-mp-date" type="date" value={taskForm.planned_mp_date} onChange={(event) => updateForm("planned_mp_date", event.target.value)} required />
                </div>
              </div>

              <SelectField label="生产线体" value={taskForm.production_line} onChange={(value) => updateForm("production_line", value)} options={productionLines} />
              {taskForm.production_line === "+ 新增线体" ? (
                <div className="new-task-field">
                  <input value={customLine} onChange={(event) => setCustomLine(event.target.value)} placeholder="请输入新增线体，如：L05" required />
                </div>
              ) : null}

              <div className="new-task-field">
                <label htmlFor="new-task-receive-date">项目接收时间 <span className="required">*</span></label>
                <input id="new-task-receive-date" type="date" value={taskForm.receive_date} onChange={(event) => updateForm("receive_date", event.target.value)} required />
                <p className="new-task-help">首批机型共用该接收时间，后续批次通过「加单」补充。</p>
              </div>

              <div className="new-task-field">
                <label>机型 <span className="required">*</span><small>至少填写 1 个</small></label>
                <div className="new-task-model-list">
                  {models.map((model, index) => (
                    <div className="new-task-model-row" key={`model-${index}`}>
                      <input value={model} onChange={(event) => updateModel(index, event.target.value)} placeholder="如 NV08126/093" required={index === 0} />
                      {models.length > 1 ? (
                        <button type="button" onClick={() => removeModel(index)} aria-label="删除机型">
                          ×
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
                <button className="new-task-link-button" type="button" onClick={addModel}>
                  + 新增机型
                </button>
              </div>

              <div className="new-task-section-title">检查信息</div>
              <div className="new-task-field">
                <label>QG 节点 <span className="required">*</span></label>
                <div className="new-task-node-select">
                  {qgNodes.map((node) => {
                    const recommended = prepareResult?.recommended_qg_node?.id === node.id;
                    return (
                      <button
                        type="button"
                        key={node.id}
                        className={String(node.id) === taskForm.qg_node_id ? "selected" : ""}
                        onClick={() => updateForm("qg_node_id", String(node.id))}
                      >
                        {node.node_code}
                        {recommended ? <span>推荐</span> : null}
                      </button>
                    );
                  })}
                </div>
                <p className="new-task-help">{prepareResult?.recommended_qg_node ? `校验链接后系统推荐 ${prepareResult.recommended_qg_node.node_code}` : "校验链接后系统将自动推荐建议节点"}</p>
              </div>
            </div>
            <footer className="new-task-modal-footer">
              <button className="new-task-secondary-button" type="button" onClick={closeModal}>
                取消
              </button>
              <button className="new-task-primary-button" type="submit" disabled={!isStepReady}>
                下一步：确认信息
              </button>
            </footer>
          </form>
        ) : (
          <>
            <div className="new-task-modal-body">
              <div className="new-task-confirm-tip">请确认以下信息无误后点击「开始执行」。点击后系统将开始后台自动检查，直接进入执行界面。</div>
              <div className="new-task-confirm-summary">
                {[
                  ["项目名称", taskForm.project_name],
                  ["客户", taskForm.customer],
                  ["项目类别", taskForm.project_category],
                  ["BU", taskForm.bu],
                  ["项目等级", taskForm.project_level],
                  ["MQ人员", selectedMqUser?.name || taskForm.mq_user_id],
                  ["对应 MP（项目经理）", taskForm.mp_owner],
                  ["小组", taskForm.group_name],
                  ["计划量产时间", taskForm.planned_mp_date],
                  ["生产线体", selectedLine],
                  ["首批接收记录", `${taskForm.receive_date} · ${cleanModels.join("、")}`],
                  ["QG 节点", selectedQGNode?.node_code || taskForm.qg_node_id],
                  ["VDrive 链接", taskForm.vdrive_url]
                ].map(([label, value]) => (
                  <p key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </p>
                ))}
              </div>
              {message ? <p className={`new-task-path-hint ${pathState}`}>{message}</p> : null}
            </div>
            <footer className="new-task-modal-footer">
              <button className="new-task-secondary-button" type="button" onClick={() => setWizardStep("edit")}>
                返回修改
              </button>
              <button className="new-task-primary-button" type="button" onClick={() => void handleCreateTask()} disabled={isSubmitting}>
                {isSubmitting ? "创建中..." : "开始执行"}
              </button>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<string | { label: string; value: string }>;
}) {
  return (
    <div className="new-task-field">
      <label>
        {label} <span className="required">*</span>
      </label>
      <select value={value} onChange={(event) => onChange(event.target.value)} required>
        <option value="">请选择</option>
        {options.map((item) => {
          const option = typeof item === "string" ? { label: item, value: item } : item;
          return (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          );
        })}
      </select>
    </div>
  );
}
