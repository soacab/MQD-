"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  addProjectOrder,
  createProject,
  deleteProject,
  getProject,
  listProjects,
  validateVdriveLink,
  type Project,
  type VDriveValidation
} from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [vdriveResult, setVdriveResult] = useState<VDriveValidation | null>(null);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    project_name: "",
    customer: "",
    vdrive_url: "",
    receive_date: "",
    models: ""
  });
  const [orderForm, setOrderForm] = useState({ receive_date: "", models: "" });

  async function refresh() {
    try {
      const rows = await listProjects();
      setProjects(rows.items);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目列表加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

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
        ...form,
        models: form.models
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      });
      setForm({ project_name: "", customer: "", vdrive_url: "", receive_date: "", models: "" });
      setVdriveResult(null);
      setMessage("项目已创建。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建项目失败");
    }
  }

  async function handleSelect(projectId: number) {
    try {
      const detail = await getProject(projectId);
      setSelectedProject(detail);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目详情加载失败");
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
    try {
      await deleteProject(selectedProject.id, {
        confirm_project_name: selectedProject.project_name,
        delete_reason: "前端最小闭环作废"
      });
      setSelectedProject(null);
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
            <input
              name="project_name"
              value={form.project_name}
              onChange={(event) => setForm({ ...form, project_name: event.target.value })}
              required
            />
          </label>
          <label>
            客户
            <input
              name="customer"
              value={form.customer}
              onChange={(event) => setForm({ ...form, customer: event.target.value })}
              required
            />
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
            <input
              name="receive_date"
              type="date"
              value={form.receive_date}
              onChange={(event) => setForm({ ...form, receive_date: event.target.value })}
              required
            />
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
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>项目</th>
                <th>客户</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} onClick={() => void handleSelect(project.id)}>
                  <td>{project.id}</td>
                  <td>{project.project_name}</td>
                  <td>{project.customer}</td>
                  <td>{project.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </section>
      {selectedProject ? (
        <section className="module spaced">
          <h2>项目详情：{selectedProject.project_name}</h2>
          <div className="detail-grid">
            <p>客户：{selectedProject.customer}</p>
            <p>状态：{selectedProject.status}</p>
            <p>VDrive：{selectedProject.vdrive?.folder_path || selectedProject.vdrive_url || "未设置"}</p>
            <p>机型：{selectedProject.models?.map((item) => item.model_name).join(" / ") || "未填写"}</p>
          </div>
          <form className="inline-form" onSubmit={handleAddOrder}>
            <input
              type="date"
              value={orderForm.receive_date}
              onChange={(event) => setOrderForm({ ...orderForm, receive_date: event.target.value })}
              required
            />
            <input
              placeholder="新增机型，逗号分隔"
              value={orderForm.models}
              onChange={(event) => setOrderForm({ ...orderForm, models: event.target.value })}
            />
            <button type="submit">保存加单</button>
            <button className="secondary-button" type="button" onClick={handleDelete}>
              作废项目
            </button>
          </form>
        </section>
      ) : null}
    </main>
  );
}
