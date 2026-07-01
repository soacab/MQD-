"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  createUser,
  deleteUser,
  disableUser,
  enableUser,
  getCurrentUser,
  getSystemSettings,
  listUsers,
  saveSystemSetting,
  updateUser,
  type User
} from "@/lib/api";
import { updateStoredUser } from "@/lib/session";

const permissionOptions = [
  { key: "inspection_engineer", label: "点检执行", description: "可以创建和执行点检任务。" },
  { key: "rules_admin", label: "规则管理", description: "可以维护检查规则。" },
  { key: "project_admin", label: "项目管理", description: "可以查看全部项目档案和管理项目记录。" },
  { key: "super_admin", label: "权限管理", description: "可以编辑后台用户、权限和系统设置。" }
];

const statusLabels: Record<string, string> = {
  active: "启用",
  disabled: "停用"
};

const emptyForm = {
  uid: "",
  name: "",
  email: "",
  status: "active",
  permissions: ["inspection_engineer"]
};

type AdminSection = "users" | "settings";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [permissionFilter, setPermissionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [autoCheckEnabled, setAutoCheckEnabled] = useState(true);
  const [activeSection, setActiveSection] = useState<AdminSection>("users");
  const [showUserModal, setShowUserModal] = useState(false);
  const [message, setMessage] = useState("");

  const canManageAccounts = Boolean(currentUser?.permissions.includes("super_admin"));
  const isEditingCurrentUser = Boolean(currentUser && editingUserId === currentUser.id);
  const activeCount = users.filter((item) => item.status === "active").length;

  async function refresh({ clearMessage = true }: { clearMessage?: boolean } = {}) {
    try {
      const me = await getCurrentUser();
      const settings = await getSystemSettings();
      setCurrentUser(me);
      setAutoCheckEnabled(Boolean(settings.auto_check_enabled));

      if (!me.permissions.includes("super_admin")) {
        setUsers([]);
        if (clearMessage) {
          setMessage("仅权限管理员可编辑用户、权限和系统设置。");
        }
        return;
      }

      const userRows = await listUsers({ keyword, permission: permissionFilter, status: statusFilter });
      setUsers(userRows.items);
      if (clearMessage) {
        setMessage("");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "后台数据加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, [keyword, permissionFilter, statusFilter]);

  function updateFormField(field: keyof typeof emptyForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function togglePermission(permission: string) {
    if (isEditingCurrentUser && permission === "super_admin" && form.permissions.includes("super_admin")) {
      setMessage("不能取消自己的权限管理权限。");
      return;
    }
    setForm((current) => {
      const permissions = current.permissions.includes(permission)
        ? current.permissions.filter((item) => item !== permission)
        : [...current.permissions, permission];
      return { ...current, permissions };
    });
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingUserId(null);
  }

  function closeUserModal() {
    resetForm();
    setShowUserModal(false);
  }

  function startCreate() {
    resetForm();
    setMessage("");
    setActiveSection("users");
    setShowUserModal(true);
  }

  function startEdit(user: User) {
    setEditingUserId(user.id);
    setForm({
      uid: user.uid,
      name: user.name,
      email: user.email || "",
      status: user.status,
      permissions: user.permissions
    });
    setMessage("");
    setShowUserModal(true);
  }

  function isCurrentUser(user: User) {
    return currentUser?.id === user.id;
  }

  function permissionLabel(permission: string) {
    return permissionOptions.find((option) => option.key === permission)?.label || permission;
  }

  async function handleSaveUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageAccounts) {
      setMessage("仅权限管理员可编辑用户和权限。");
      return;
    }
    if (!form.permissions.length) {
      setMessage("请至少选择一个用户权限。");
      return;
    }
    if (isEditingCurrentUser && form.status !== "active") {
      setMessage("不能停用当前登录账号。");
      return;
    }
    if (isEditingCurrentUser && !form.permissions.includes("super_admin")) {
      setMessage("不能取消自己的权限管理权限。");
      return;
    }

    try {
      if (editingUserId) {
        const savedUser = await updateUser(editingUserId, {
          name: form.name,
          email: form.email,
          status: form.status,
          permissions: form.permissions
        });
        if (currentUser?.id === savedUser.id) {
          updateStoredUser(savedUser);
          setCurrentUser(savedUser);
        }
        setMessage("账号已更新。");
      } else {
        await createUser({
          uid: form.uid,
          name: form.name,
          email: form.email,
          status: form.status,
          permissions: form.permissions
        });
        setMessage("账号已保存。");
      }
      closeUserModal();
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存账号失败");
    }
  }

  async function handleToggleStatus(user: User) {
    if (!canManageAccounts) {
      setMessage("仅权限管理员可编辑用户和权限。");
      return;
    }
    if (isCurrentUser(user)) {
      setMessage("不能停用当前登录账号。");
      return;
    }
    try {
      if (user.status === "active") {
        await disableUser(user.id);
        setMessage("账号已停用。");
      } else {
        await enableUser(user.id);
        setMessage("账号已启用。");
      }
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号状态更新失败");
    }
  }

  async function handleDelete(user: User) {
    if (!canManageAccounts) {
      setMessage("仅权限管理员可编辑用户和权限。");
      return;
    }
    if (isCurrentUser(user)) {
      setMessage("不能删除当前登录账号。");
      return;
    }
    const confirmed = window.confirm(`确认删除 UID\n\n${user.name} · ${user.uid}\n\n删除后该 UID 将无法登录 CheckFlow，历史检查记录和报告数据会保留。`);
    if (!confirmed) {
      return;
    }
    try {
      await deleteUser(user.id);
      setMessage("UID 已删除。");
      if (editingUserId === user.id) {
        closeUserModal();
      }
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除账号失败");
    }
  }

  async function handleSaveSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageAccounts) {
      setMessage("仅权限管理员可保存系统设置。");
      return;
    }
    try {
      await saveSystemSetting("auto_check_enabled", autoCheckEnabled);
      setMessage("系统设置已保存。");
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存设置失败");
    }
  }

  return (
    <main className="account-page">
      <section className="account-body">
        <aside className="account-sidebar" aria-label="后台管理导航">
          <div className="account-sidebar-title">
            后台管理
            <div className="account-sidebar-sub">账号权限与全局设置</div>
          </div>
          <nav className="account-side-nav">
            <button
              className={`account-nav-btn ${activeSection === "users" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveSection("users")}
            >
              用户与权限
            </button>
            <button
              className={`account-nav-btn ${activeSection === "settings" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveSection("settings")}
            >
              系统设置
            </button>
          </nav>
        </aside>

        <div className="account-content">
          {message ? <p className="account-notice">{message}</p> : null}

          {activeSection === "users" ? (
            <section className="account-view active" aria-label="用户与权限">
              <div className="account-user-layout">
                <section className="account-main">
                  <div className="account-head">
                    <div>
                      <h1 className="account-title">用户与权限</h1>
                      <div className="account-sub">共 {users.length} 个账号 · 启用 {activeCount} 个</div>
                      {!canManageAccounts ? (
                        <div className="account-readonly-note">仅权限管理员可编辑用户和权限</div>
                      ) : null}
                    </div>
                    <div className="account-filters">
                      <input
                        id="account-search"
                        className="account-control"
                        aria-label="搜索 UID、姓名、邮箱"
                        placeholder="搜索 UID / 姓名 / 邮箱"
                        value={keyword}
                        onChange={(event) => setKeyword(event.target.value)}
                      />
                      <select
                        id="account-permission-filter"
                        className="account-control"
                        aria-label="权限筛选"
                        value={permissionFilter}
                        onChange={(event) => setPermissionFilter(event.target.value)}
                      >
                        <option value="">全部权限</option>
                        {permissionOptions.map((permission) => (
                          <option key={permission.key} value={permission.key}>
                            {permission.label}
                          </option>
                        ))}
                      </select>
                      <select
                        id="account-status-filter"
                        className="account-control"
                        aria-label="状态筛选"
                        value={statusFilter}
                        onChange={(event) => setStatusFilter(event.target.value)}
                      >
                        <option value="">全部状态</option>
                        <option value="active">启用</option>
                        <option value="disabled">停用</option>
                      </select>
                      <button className="account-primary-button" type="button" onClick={startCreate} disabled={!canManageAccounts}>
                        添加用户
                      </button>
                    </div>
                  </div>

                  <div className="account-table-wrap">
                    <table className="account-table">
                      <thead>
                        <tr>
                          <th>UID</th>
                          <th>姓名</th>
                          <th>公司邮箱</th>
                          <th>权限</th>
                          <th>状态</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {users.length ? (
                          users.map((item) => (
                            <tr key={item.id}>
                              <td>
                                <span className="account-name">{item.uid}</span>
                              </td>
                              <td>{item.name}</td>
                              <td className="account-email">{item.email || "-"}</td>
                              <td>
                                <div className="account-permissions">
                                  {item.permissions.map((permission) => (
                                    <span className={`account-permission-chip ${permission}`} key={permission}>
                                      {permissionLabel(permission)}
                                    </span>
                                  ))}
                                </div>
                              </td>
                              <td>
                                <span className={`account-status ${item.status}`}>{statusLabels[item.status] || item.status}</span>
                              </td>
                              <td>
                                <div className="account-action-row">
                                  <button className="account-action" type="button" onClick={() => startEdit(item)} disabled={!canManageAccounts}>
                                    编辑
                                  </button>
                                  <button
                                    className={`account-action ${item.status === "active" ? "warn" : ""}`}
                                    type="button"
                                    onClick={() => handleToggleStatus(item)}
                                    disabled={!canManageAccounts || isCurrentUser(item)}
                                  >
                                    {item.status === "active" ? "停用" : "启用"}
                                  </button>
                                  <button
                                    className="account-action danger"
                                    type="button"
                                    onClick={() => handleDelete(item)}
                                    disabled={!canManageAccounts || isCurrentUser(item)}
                                  >
                                    删除
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="account-empty" colSpan={6}>
                              没有符合条件的账号
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                <aside className="permission-list" aria-label="权限说明">
                  <div className="permission-list-title">权限说明</div>
                  {permissionOptions.map((permission) => (
                    <div className="permission-row" key={permission.key}>
                      <div className={`permission-role ${permission.key}`}>{permission.label}</div>
                      <div className="permission-text">{permission.description}</div>
                    </div>
                  ))}
                </aside>
              </div>
            </section>
          ) : (
            <section className="account-view active" aria-label="系统设置">
              <section className="account-panel">
                <div className="account-head account-head-plain">
                  <div>
                    <h1 className="account-title">系统设置</h1>
                    <div className="account-sub">所有用户可查看，只有权限管理员可保存修改。</div>
                    {!canManageAccounts ? (
                      <div className="account-readonly-note">仅权限管理员可保存系统设置</div>
                    ) : null}
                  </div>
                </div>

                <form className="backend-settings" onSubmit={handleSaveSetting}>
                  <label className="backend-setting-card">
                    <span>
                      <span className="backend-settings-title">自动检查开关</span>
                      <span className="backend-settings-copy">开启后，系统允许自动执行检查流程。</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={autoCheckEnabled}
                      onChange={(event) => setAutoCheckEnabled(event.target.checked)}
                      disabled={!canManageAccounts}
                    />
                  </label>
                  <button className="account-primary-button settings-save-button" type="submit" disabled={!canManageAccounts}>
                    保存设置
                  </button>
                </form>
              </section>
            </section>
          )}
        </div>
      </section>

      {showUserModal ? (
        <div className="account-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && closeUserModal()}>
          <form className="account-modal" role="dialog" aria-modal="true" aria-labelledby="account-form-title" onSubmit={handleSaveUser}>
            <header className="account-modal-header">
              <div>
                <h2 id="account-form-title">{editingUserId ? `编辑账号 · ${form.uid}` : "添加用户"}</h2>
                <p>账号权限在 CheckFlow 内维护，变更后下次登录生效。</p>
              </div>
              <button className="account-modal-close" type="button" onClick={closeUserModal} aria-label="关闭">
                x
              </button>
            </header>

            <div className="account-modal-body">
              <label className="account-form-field">
                <span>姓名 <strong>*</strong></span>
                <input
                  name="name"
                  value={form.name}
                  onChange={(event) => updateFormField("name", event.target.value)}
                  disabled={!canManageAccounts}
                  placeholder="请输入姓名"
                  required
                />
              </label>
              <label className="account-form-field">
                <span>UID <strong>*</strong></span>
                <input
                  name="uid"
                  value={form.uid}
                  onChange={(event) => updateFormField("uid", event.target.value)}
                  disabled={Boolean(editingUserId) || !canManageAccounts}
                  placeholder="如 UID02322"
                  required
                />
              </label>
              <label className="account-form-field">
                <span>公司邮箱</span>
                <input
                  name="email"
                  value={form.email}
                  onChange={(event) => updateFormField("email", event.target.value)}
                  disabled={!canManageAccounts}
                  placeholder="如 uid02322@company.com"
                />
              </label>

              <fieldset className="account-form-field">
                <legend>用户权限</legend>
                <div className="account-permission-checks">
                  {permissionOptions.map((permission) => (
                    <label className="account-check" key={permission.key}>
                      <input
                        type="checkbox"
                        checked={form.permissions.includes(permission.key)}
                        onChange={() => togglePermission(permission.key)}
                        disabled={!canManageAccounts || (isEditingCurrentUser && permission.key === "super_admin")}
                      />
                      {permission.label}
                    </label>
                  ))}
                </div>
              </fieldset>

              <fieldset className="account-form-field">
                <legend>状态</legend>
                <div className="account-status-radios">
                  <label className="account-radio">
                    <input
                      type="radio"
                      name="account-status"
                      value="active"
                      checked={form.status === "active"}
                      onChange={(event) => updateFormField("status", event.target.value)}
                      disabled={!canManageAccounts || isEditingCurrentUser}
                    />
                    启用
                  </label>
                  <label className="account-radio">
                    <input
                      type="radio"
                      name="account-status"
                      value="disabled"
                      checked={form.status === "disabled"}
                      onChange={(event) => updateFormField("status", event.target.value)}
                      disabled={!canManageAccounts || isEditingCurrentUser}
                    />
                    停用
                  </label>
                </div>
              </fieldset>
            </div>

            <footer className="account-modal-footer">
              <button className="account-secondary-button" type="button" onClick={closeUserModal}>
                取消
              </button>
              <button className="account-primary-button" type="submit" disabled={!canManageAccounts}>
                保存用户
              </button>
            </footer>
          </form>
        </div>
      ) : null}
    </main>
  );
}
