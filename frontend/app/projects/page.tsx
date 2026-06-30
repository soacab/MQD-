"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  addProjectOrder,
  createProject,
  deleteProject,
  getProject,
  listProjects,
  updateProject,
  updateProjectVdrive,
  validateVdriveLink,
  type Project,
  type VDriveValidation
} from "@/lib/api";

const emptyProjectForm = {
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
  vdrive_url: "",
  receive_date: "",
  models: ""
};

const editableProjectFields = [
  "project_name",
  "customer",
  "project_category",
  "bu",
  "project_level",
  "mq_user_id",
  "mp_owner",
  "group_name",
  "planned_mp_date",
  "production_line"
] as const;

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [vdriveResult, setVdriveResult] = useState<VDriveValidation | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState(emptyProjectForm);
  const [editForm, setEditForm] = useState(emptyProjectForm);
  const [editVdriveUrl, setEditVdriveUrl] = useState("");
  const [listFilters, setListFilters] = useState({ keyword: "", status: "normal", qg_node_id: "", mq_user_id: "" });
  const [orderForm, setOrderForm] = useState({ receive_date: "", models: "" });

  async function refresh(filters = listFilters) {
    try {
      const rows = await listProjects(filters);
      setProjects(rows.items);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目列表加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  function buildProjectPayload(source: typeof emptyProjectForm) {
    return {
      project_name: source.project_name,
      customer: source.customer,
      project_category: source.project_category || null,
      bu: source.bu || null,
      project_level: source.project_level || null,
      mq_user_id: source.mq_user_id ? Number(source.mq_user_id) : null,
      mp_owner: source.mp_owner || null,
      group_name: source.group_name || null,
      planned_mp_date: source.planned_mp_date || null,
      production_line: source.production_line || null
    };
  }

  function fillEditForm(project: Project) {
    setEditForm({
      ...emptyProjectForm,
      project_name: project.project_name || "",
      customer: project.customer || "",
      project_category: project.project_category || "",
      bu: project.bu || "",
      project_level: project.project_level || "",
      mq_user_id: project.mq_user_id ? String(project.mq_user_id) : "",
      mp_owner: project.mp_owner || "",
      group_name: project.group_name || "",
      planned_mp_date: project.planned_mp_date || "",
      production_line: project.production_line || ""
    });
    setEditVdriveUrl(project.vdrive?.url || project.vdrive_url || "");
  }

  async function handleValidate() {
    try {
      const result = await validateVdriveLink(form.vdrive_url);
      setVdriveResult(result);
      setMessage("VDrive 链接校验通过。");
    } catch (error) {
      setVdriveResult(null);
      setMessage(error instanceof Error ? error.message : "VDrive 校验失败");
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await createProject({
        ...buildProjectPayload(form),
        vdrive_url: form.vdrive_url,
        receive_date: form.receive_date,
        models: form.models
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      });
      setForm(emptyProjectForm);
      setVdriveResult(null);
      setMessage("项目已创建。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建项目失败");
    }
  }

  async function handleFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await refresh(listFilters);
  }

  async function handleSelect(projectId: number) {
    try {
      const detail = await getProject(projectId);
      setSelectedProject(detail);
      fillEditForm(detail);
      setDeleteConfirmName("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目详情加载失败");
    }
  }

  async function handleSaveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) {
      return;
    }
    try {
      const detail = await updateProject(selectedProject.id, buildProjectPayload(editForm));
      setSelectedProject(detail);
      fillEditForm(detail);
      setMessage("项目基础信息已更新。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目基础信息更新失败");
    }
  }

  async function handleUpdateVdrive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) {
      return;
    }
    try {
      const detail = await updateProjectVdrive(selectedProject.id, { vdrive_url: editVdriveUrl });
      setSelectedProject(detail);
      fillEditForm(detail);
      setMessage("VDrive 链接已更新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "VDrive 链接更新失败");
    }
  }

  async function handleAddOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) {
      return;
    }
    try {
      await addProjectOrder(selectedProject.id, {
        receive_date: orderForm.receive_date,
        models: orderForm.models
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      });
      setOrderForm({ receive_date: "", models: "" });
      setMessage("加单已保存。");
      await handleSelect(selectedProject.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加单失败");
    }
  }

  async function handleDelete() {
    if (!selectedProject) {
      return;
    }
    if (deleteConfirmName !== selectedProject.project_name) {
      setMessage("请手动输入项目名称确认作废。");
      return;
    }
    try {
      await deleteProject(selectedProject.id, {
        confirm_project_name: deleteConfirmName,
        delete_reason: "前端最小闭环作废"
      });
      setSelectedProject(null);
      setDeleteConfirmName("");
      setMessage("项目已作废。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目作废失败");
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">项目</p>
        <h1>项目管理</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <section className="two-column">
        <form className="form-panel" onSubmit={handleCreate}>
          <h2>创建项目</h2>
          <label>
            项目名称
            <input name="project_name" value={form.project_name} onChange={(event) => setForm({ ...form, project_name: event.target.value })} required />
          </label>
          <label>
            客户
            <input name="customer" value={form.customer} onChange={(event) => setForm({ ...form, customer: event.target.value })} required />
          </label>
          <label>
            项目类别
            <input name="project_category" value={form.project_category} onChange={(event) => setForm({ ...form, project_category: event.target.value })} />
          </label>
          <label>
            BU
            <input name="bu" value={form.bu} onChange={(event) => setForm({ ...form, bu: event.target.value })} />
          </label>
          <label>
            项目等级
            <input name="project_level" value={form.project_level} onChange={(event) => setForm({ ...form, project_level: event.target.value })} />
          </label>
          <label>
            MQ 人员 ID
            <input name="mq_user_id" value={form.mq_user_id} onChange={(event) => setForm({ ...form, mq_user_id: event.target.value })} />
          </label>
          <label>
            对应 MP
            <input name="mp_owner" value={form.mp_owner} onChange={(event) => setForm({ ...form, mp_owner: event.target.value })} />
          </label>
          <label>
            小组
            <input name="group_name" value={form.group_name} onChange={(event) => setForm({ ...form, group_name: event.target.value })} />
          </label>
          <label>
            计划量产时间
            <input name="planned_mp_date" type="date" value={form.planned_mp_date} onChange={(event) => setForm({ ...form, planned_mp_date: event.target.value })} />
          </label>
          <label>
            生产线体
            <input name="production_line" value={form.production_line} onChange={(event) => setForm({ ...form, production_line: event.target.value })} />
          </label>
          <label>
            VDrive 链接
            <input
              name="vdrive_url"
              value={form.vdrive_url}
              onChange={(event) => setForm({ ...form, vdrive_url: event.target.value })}
              placeholder="https://vdrive.example/folderGuid=demo"
              required
            />
          </label>
          <label>
            接收日期
            <input name="receive_date" type="date" value={form.receive_date} onChange={(event) => setForm({ ...form, receive_date: event.target.value })} required />
          </label>
          <label>
            机型（逗号分隔）
            <input name="models" value={form.models} onChange={(event) => setForm({ ...form, models: event.target.value })} />
          </label>
          <div className="button-row">
            <button type="button" onClick={handleValidate}>
              校验路径
            </button>
            <button type="submit">创建项目</button>
          </div>
          {vdriveResult ? <p className="notice">已识别：{vdriveResult.folder_path}</p> : null}
        </form>
        <section className="module">
          <h2>项目列表</h2>
          <form className="inline-form" onSubmit={handleFilter}>
            <input placeholder="项目 / 客户 / 机型" value={listFilters.keyword} onChange={(event) => setListFilters({ ...listFilters, keyword: event.target.value })} />
            <select value={listFilters.status} onChange={(event) => setListFilters({ ...listFilters, status: event.target.value })}>
              <option value="normal">normal</option>
              <option value="deleted">deleted</option>
            </select>
            <input placeholder="QG 节点 ID" value={listFilters.qg_node_id} onChange={(event) => setListFilters({ ...listFilters, qg_node_id: event.target.value })} />
            <input placeholder="MQ 人员 ID" value={listFilters.mq_user_id} onChange={(event) => setListFilters({ ...listFilters, mq_user_id: event.target.value })} />
            <button type="submit">筛选</button>
          </form>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>项目</th>
                <th>客户</th>
                <th>状态</th>
                <th>MQ</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} onClick={() => void handleSelect(project.id)}>
                  <td>{project.id}</td>
                  <td>{project.project_name}</td>
                  <td>{project.customer}</td>
                  <td>{project.status}</td>
                  <td>{project.mq_user_name_snapshot || project.mq_user_id || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </section>
      {selectedProject ? (
        <section className="two-column spaced">
          <section className="module">
            <h2>项目详情：{selectedProject.project_name}</h2>
            <div className="detail-grid">
              <p>客户：{selectedProject.customer}</p>
              <p>状态：{selectedProject.status}</p>
              <p>项目类别：{selectedProject.project_category || "-"}</p>
              <p>BU：{selectedProject.bu || "-"}</p>
              <p>项目等级：{selectedProject.project_level || "-"}</p>
              <p>MQ：{selectedProject.mq_user_name_snapshot || selectedProject.mq_user_id || "-"}</p>
              <p>MP：{selectedProject.mp_owner || "-"}</p>
              <p>小组：{selectedProject.group_name || "-"}</p>
              <p>计划量产时间：{selectedProject.planned_mp_date || "-"}</p>
              <p>生产线体：{selectedProject.production_line || "-"}</p>
              <p>VDrive：{selectedProject.vdrive?.folder_path || selectedProject.vdrive_url || "未设置"}</p>
              <p>机型：{selectedProject.models?.map((item) => item.model_name).join(" / ") || "未填写"}</p>
            </div>
            <h3>接收批次</h3>
            <ul className="plain-list">
              {selectedProject.orders?.map((order) => (
                <li key={order.id}>批次 {order.id}：{order.receive_date}</li>
              )) || null}
            </ul>
            <form className="inline-form" onSubmit={handleAddOrder}>
              <input type="date" value={orderForm.receive_date} onChange={(event) => setOrderForm({ ...orderForm, receive_date: event.target.value })} required />
              <input placeholder="新增机型，逗号分隔" value={orderForm.models} onChange={(event) => setOrderForm({ ...orderForm, models: event.target.value })} />
              <button type="submit">保存加单</button>
            </form>
            <div className="inline-form">
              <input
                aria-label="手动输入项目名称"
                placeholder={`手动输入项目名称：${selectedProject.project_name}`}
                value={deleteConfirmName}
                onChange={(event) => setDeleteConfirmName(event.target.value)}
              />
              <button className="secondary-button" type="button" onClick={handleDelete} disabled={deleteConfirmName !== selectedProject.project_name}>
                作废项目
              </button>
            </div>
          </section>
          <section className="module">
            <h2>编辑项目</h2>
            <form className="form-panel" onSubmit={handleSaveProject}>
              {editableProjectFields.map((field) => (
                <label key={field}>
                  {field}
                  <input
                    name={field}
                    type={field === "planned_mp_date" ? "date" : "text"}
                    value={editForm[field]}
                    onChange={(event) => setEditForm({ ...editForm, [field]: event.target.value })}
                    required={field === "project_name" || field === "customer"}
                  />
                </label>
              ))}
              <button type="submit">保存基础信息</button>
            </form>
            <form className="inline-form" onSubmit={handleUpdateVdrive}>
              <input value={editVdriveUrl} onChange={(event) => setEditVdriveUrl(event.target.value)} placeholder="新的 VDrive 链接" required />
              <button type="submit">更新 VDrive</button>
            </form>
          </section>
        </section>
      ) : null}
    </main>
  );
}
