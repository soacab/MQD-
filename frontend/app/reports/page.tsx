"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  addProjectOrder,
  deleteProject,
  getCurrentUser,
  getProject,
  getReport,
  listArchiveProjects,
  listBusinessUserOptions,
  listQGNodes,
  type ArchiveProject,
  type BusinessUserOption,
  type Project,
  type QGNode,
  type Report,
  type User
} from "@/lib/api";

const resultLabels: Record<string, string> = {
  FULL_GO: "FULL-GO",
  C_GO: "C-GO",
  NO_GO: "NO-GO"
};

const emptyArchiveFilters = {
  keyword: "",
  mq_user_id: "",
  qg_node_id: "",
  overall_result: "",
  modified_from: "",
  modified_to: "",
  page: "1",
  page_size: "10"
};

function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

function escapeExcelCell(value: unknown) {
  const text = String(value ?? "");
  const safeText = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return safeText
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function downloadHtmlTable(filename: string, headers: string[], rows: Array<Array<string | number | null | undefined>>) {
  const head = headers.map((header) => `<th>${escapeExcelCell(header)}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${escapeExcelCell(cell ?? "-")}</td>`).join("")}</tr>`)
    .join("");
  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>table{border-collapse:collapse}th,td{border:1px solid #dde1e8;padding:6px 10px;mso-number-format:"\\@"}th{background:#eef0ff;font-weight:700}</style></head><body><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></body></html>`;
  const blob = new Blob(["\ufeff", html], { type: "application/vnd.ms-excel;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const [archiveRows, setArchiveRows] = useState<ArchiveProject[]>([]);
  const [qgNodes, setQgNodes] = useState<QGNode[]>([]);
  const [users, setUsers] = useState<BusinessUserOption[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [archiveFilters, setArchiveFilters] = useState(emptyArchiveFilters);
  const [message, setMessage] = useState("");
  const [total, setTotal] = useState(0);
  const [addOrderForm, setAddOrderForm] = useState({ receive_date: "", models: "" });
  const [isAddingOrder, setIsAddingOrder] = useState(false);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");

  const canManageProjects = currentUser?.permissions.includes("project_admin");
  const canAddOrder =
    currentUser?.permissions.includes("inspection_engineer") || currentUser?.permissions.includes("project_admin");
  const page = Number(archiveFilters.page || "1");
  const pageSize = Number(archiveFilters.page_size || "10");
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  async function refresh(filters = archiveFilters) {
    try {
      const rows = await listArchiveProjects(filters);
      setArchiveRows(rows.items);
      setTotal(rows.total || rows.items.length);
      setMessage("");
      return true;
    } catch (error) {
      setArchiveRows([]);
      setMessage(error instanceof Error ? error.message : "检查档案加载失败");
      return false;
    }
  }

  async function loadOptions() {
    try {
      const [nodeRows, userRows, me] = await Promise.all([listQGNodes(), listBusinessUserOptions(), getCurrentUser()]);
      setQgNodes(nodeRows.items);
      setUsers(userRows.items);
      setCurrentUser(me);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "筛选选项加载失败");
    }
  }

  useEffect(() => {
    void refresh();
    void loadOptions();
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextFilters = { ...archiveFilters, page: "1" };
    setArchiveFilters(nextFilters);
    await refresh(nextFilters);
  }

  async function handlePage(nextPage: number) {
    const safePage = String(Math.min(Math.max(1, nextPage), totalPages));
    const nextFilters = { ...archiveFilters, page: safePage };
    setArchiveFilters(nextFilters);
    await refresh(nextFilters);
  }

  async function handleResetDates() {
    const nextFilters = { ...archiveFilters, modified_from: "", modified_to: "", page: "1" };
    setArchiveFilters(nextFilters);
    await refresh(nextFilters);
  }

  async function handleProjectDetail(projectId: number) {
    try {
      const detail = await getProject(projectId);
      setSelectedProject(detail);
      setAddOrderForm({ receive_date: "", models: "" });
      setDeleteConfirmName("");
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目详情加载失败");
    }
  }

  async function handleOpenReport(reportId: number) {
    try {
      setSelectedReport(await getReport(reportId));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告加载失败");
    }
  }

  async function handleAddOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject || isAddingOrder) {
      return;
    }
    const models = addOrderForm.models
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!models.length) {
      setMessage("至少填写 1 个新增机型。");
      return;
    }
    try {
      setIsAddingOrder(true);
      await addProjectOrder(selectedProject.id, {
        receive_date: addOrderForm.receive_date,
        models
      });
      try {
        const detail = await getProject(selectedProject.id);
        setSelectedProject(detail);
        const refreshed = await refresh();
        setMessage(refreshed ? "加单已保存。" : "加单已保存，但档案列表刷新失败。");
      } catch (refreshError) {
        setMessage(refreshError instanceof Error ? `加单已保存，但项目详情刷新失败：${refreshError.message}` : "加单已保存，但项目详情刷新失败");
      }
      setAddOrderForm({ receive_date: "", models: "" });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加单失败");
    } finally {
      setIsAddingOrder(false);
    }
  }

  async function handleDeleteProject() {
    if (!selectedProject) {
      return;
    }
    if (deleteConfirmName !== selectedProject.project_name) {
      setMessage("请手动输入项目名称确认删除。");
      return;
    }
    try {
      await deleteProject(selectedProject.id, {
        confirm_project_name: deleteConfirmName,
        delete_reason: "检查档案项目详情删除"
      });
      setSelectedProject(null);
      setDeleteConfirmName("");
      try {
        const refreshed = await refresh();
        setMessage(refreshed ? "项目已删除。" : "项目已删除，但档案列表刷新失败。");
      } catch {
        setMessage("项目已删除，但档案列表刷新失败。");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目删除失败");
    }
  }

  async function handleExportExcel() {
    try {
      const exportFilters = { ...archiveFilters, page: "1" };
      const probe = await listArchiveProjects({ ...exportFilters, page_size: "1" });
      const exportTotal = probe.total || probe.items.length;
      const rows =
        exportTotal > probe.items.length
          ? await listArchiveProjects({ ...exportFilters, page_size: String(exportTotal) })
          : probe;
      const exportRows = rows.items.map((row) => [
        row.project_name,
        row.models.join("、") || "-",
        formatDate(row.project_created_at),
        row.qg_node.node_code,
        resultLabels[row.overall_result] || row.overall_result,
        formatDate(row.report_last_modified_at),
        row.mq_user_name || "-"
      ]);
      downloadHtmlTable(
        `CheckFlow_检查档案_${new Date().toISOString().slice(0, 10).replaceAll("-", "")}.xls`,
        ["项目名称", "机型", "项目创建时间", "当前QG节点", "本轮结论", "报告修改时间", "MQ人员"],
        exportRows
      );
      setMessage(`已导出 ${rows.items.length} 条检查档案。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出 Excel 失败");
    }
  }

  return (
    <main className="page archive-shell">
      <p className="field-governance-note">
        字段治理：检查档案列表字段按方案 4.7 与原型对齐；接口中的内部 ID、规则快照 JSON 和未完成更正能力不作为正式展示字段。
      </p>
      <form className="archive-toolbar" onSubmit={handleSearch}>
        <input
          aria-label="项目名称或机型"
          placeholder="项目名称或机型"
          value={archiveFilters.keyword}
          onChange={(event) => setArchiveFilters({ ...archiveFilters, keyword: event.target.value })}
        />
        <select
          aria-label="MQ 人员"
          value={archiveFilters.mq_user_id}
          onChange={(event) => setArchiveFilters({ ...archiveFilters, mq_user_id: event.target.value })}
        >
          <option value="">全部MQ人员</option>
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {user.name}
            </option>
          ))}
        </select>
        <select
          aria-label="QG 节点"
          value={archiveFilters.qg_node_id}
          onChange={(event) => setArchiveFilters({ ...archiveFilters, qg_node_id: event.target.value })}
        >
          <option value="">全部QG节点</option>
          {qgNodes.map((node) => (
            <option key={node.id} value={node.id}>
              {node.node_code}
            </option>
          ))}
        </select>
        <select
          aria-label="QG 结论"
          value={archiveFilters.overall_result}
          onChange={(event) => setArchiveFilters({ ...archiveFilters, overall_result: event.target.value })}
        >
          <option value="">全部QG结论</option>
          <option value="FULL_GO">FULL-GO</option>
          <option value="C_GO">C-GO</option>
          <option value="NO_GO">NO-GO</option>
        </select>
        <label className="archive-date-range">
          <span>选择日期范围</span>
          <input
            aria-label="报告修改开始日期"
            type="date"
            value={archiveFilters.modified_from}
            onChange={(event) => setArchiveFilters({ ...archiveFilters, modified_from: event.target.value })}
          />
          <input
            aria-label="报告修改结束日期"
            type="date"
            value={archiveFilters.modified_to}
            onChange={(event) => setArchiveFilters({ ...archiveFilters, modified_to: event.target.value })}
          />
        </label>
        <button type="button" className="secondary-button" onClick={() => void handleResetDates()}>
          重置日期
        </button>
        <button type="button" className="archive-export" onClick={() => void handleExportExcel()}>
          导出 Excel
        </button>
        <button type="submit">筛选</button>
      </form>

      {message ? <p className="notice">{message}</p> : null}

      <section className="archive-table-card">
        <table className="archive-table">
          <thead>
            <tr>
              <th>项目名称</th>
              <th>机型</th>
              <th>项目创建时间</th>
              <th>当前QG节点</th>
              <th>本轮结论</th>
              <th>报告修改时间</th>
              <th>MQ人员</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {archiveRows.length ? (
              archiveRows.map((row) => (
                <tr key={row.project_id}>
                  <td>
                    <span className="archive-project-name">{row.project_name}</span>
                  </td>
                  <td>
                    <span className="archive-model-tags">
                      {row.models.slice(0, 1).map((model) => (
                        <span className="archive-model-tag" key={model}>
                          {model}
                        </span>
                      ))}
                      {row.models.length > 1 ? <span className="archive-model-more">+{row.models.length - 1}</span> : null}
                    </span>
                  </td>
                  <td>{formatDate(row.project_created_at)}</td>
                  <td>
                    <span className="archive-node-link">{row.qg_node.node_code}</span>
                  </td>
                  <td>
                    <span className={`archive-result-pill ${row.overall_result.toLowerCase().replace("_", "-")}`}>
                      {resultLabels[row.overall_result] || row.overall_result}
                    </span>
                  </td>
                  <td>{formatDate(row.report_last_modified_at)}</td>
                  <td className="archive-owner">{row.mq_user_name || "-"}</td>
                  <td>
                    <span className="archive-action-cell">
                      <button type="button" onClick={() => void handleProjectDetail(row.project_id)}>
                        项目详情
                      </button>
                      <span className="archive-action-divider" />
                      <button type="button" onClick={() => void handleOpenReport(row.latest_report_id)}>
                        报告
                      </button>
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="archive-empty-row" colSpan={8}>
                  没有符合条件的检查档案
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <footer className="archive-pagination">
          <span>共 {total} 条记录</span>
          <div>
            <button type="button" onClick={() => void handlePage(page - 1)} disabled={page <= 1}>
              &lt; 上一页
            </button>
            <strong>{page}</strong>
            <button type="button" onClick={() => void handlePage(page + 1)} disabled={page >= totalPages}>
              下一页 &gt;
            </button>
          </div>
          <span>
            第 {page} 页 / 共 {totalPages} 页
          </span>
        </footer>
      </section>

      {selectedProject ? (
        <div className="archive-modal-backdrop" role="dialog" aria-modal="true" aria-label="项目详情">
          <section className="archive-modal">
            <header>
              <div>
                <h2>项目详情</h2>
                <p>{selectedProject.project_name}</p>
              </div>
              <button type="button" onClick={() => setSelectedProject(null)} aria-label="关闭项目详情">
                x
              </button>
            </header>
            <div className="archive-modal-body">
              <div className="archive-section-label">基础信息</div>
              <div className="archive-detail-grid">
                {[
                  ["客户", selectedProject.customer],
                  ["项目类别", selectedProject.project_category || "-"],
                  ["BU", selectedProject.bu || "-"],
                  ["项目等级", selectedProject.project_level || "-"],
                  ["MQ人员", selectedProject.mq_user_name_snapshot || selectedProject.mq_user_id || "-"],
                  ["对应 MP", selectedProject.mp_owner || "-"],
                  ["小组", selectedProject.group_name || "-"],
                  ["计划量产时间", selectedProject.planned_mp_date || "-"],
                  ["生产线体", selectedProject.production_line || "-"],
                  ["VDrive 路径", selectedProject.vdrive?.folder_path || selectedProject.vdrive_url || "-"]
                ].map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>

              <div className="archive-modal-heading">
                <span className="archive-section-label">机型 & 加单记录</span>
              </div>
              <div className="archive-order-list">
                <div className="archive-order-head">
                  <span>项目接收时间</span>
                  <span>机型</span>
                </div>
                {selectedProject.orders?.length ? (
                  selectedProject.orders.map((order) => (
                    <div className="archive-order-row" key={order.id}>
                      <span>{formatDate(order.receive_date)}</span>
                      <span>
                        {selectedProject.models
                          ?.filter((model) => !model.project_order_id || model.project_order_id === order.id)
                          .map((model) => (
                            <em key={model.id}>{model.model_name}</em>
                          ))}
                        {selectedProject.models?.some((model) => !model.project_order_id || model.project_order_id === order.id) ? null : "-"}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="archive-order-row">
                    <span>-</span>
                    <span>-</span>
                  </div>
                )}
              </div>

              {canAddOrder ? (
                <form className="archive-add-order" onSubmit={handleAddOrder}>
                  <input
                    aria-label="新增项目接收时间"
                    type="date"
                    value={addOrderForm.receive_date}
                    onChange={(event) => setAddOrderForm({ ...addOrderForm, receive_date: event.target.value })}
                    required
                  />
                  <input
                    aria-label="新增机型"
                    placeholder="新增机型，逗号分隔"
                    value={addOrderForm.models}
                    onChange={(event) => setAddOrderForm({ ...addOrderForm, models: event.target.value })}
                    required
                  />
                  <button type="submit" disabled={isAddingOrder}>
                    {isAddingOrder ? "保存中..." : "+ 加单"}
                  </button>
                </form>
              ) : null}

              {canManageProjects ? (
                <div className="archive-delete-box">
                  <p>删除项目后，普通检查档案列表不再展示该项目。</p>
                  <input
                    aria-label="手动输入项目名称"
                    placeholder={`手动输入项目名称：${selectedProject.project_name}`}
                    value={deleteConfirmName}
                    onChange={(event) => setDeleteConfirmName(event.target.value)}
                  />
                  <button type="button" onClick={() => void handleDeleteProject()} disabled={deleteConfirmName !== selectedProject.project_name}>
                    删除项目
                  </button>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {selectedReport ? (
        <div className="archive-modal-backdrop" role="dialog" aria-modal="true" aria-label="报告摘要">
          <section className="archive-modal compact">
            <header>
              <div>
                <h2>报告</h2>
                <p>{selectedReport.report_no}</p>
              </div>
              <button type="button" onClick={() => setSelectedReport(null)} aria-label="关闭报告">
                x
              </button>
            </header>
            <div className="archive-modal-body">
              <div className="stack">
                <p>项目：{selectedReport.project?.project_name || selectedReport.project_id}</p>
                <p>QG 节点：{selectedReport.qg_node?.node_code || selectedReport.qg_node_id}</p>
                <p>综合结论：{resultLabels[selectedReport.overall_result || ""] || selectedReport.overall_result || "-"}</p>
                <p>规则版本：{selectedReport.business_rule_version_no}</p>
                <p>检查项：{selectedReport.items?.length || 0} 项</p>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
