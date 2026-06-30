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

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [permissionFilter, setPermissionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [autoCheckEnabled, setAutoCheckEnabled] = useState(true);
  const [message, setMessage] = useState("");

  const canManageAccounts = Boolean(currentUser?.permissions.includes("super_admin"));
  const isEditingCurrentUser = Boolean(currentUser && editingUserId === currentUser.id);
  const activeCount = users.filter((item) => item.status === "active").length;

  async function refresh({ clearMessage = true }: { clearMessage?: boolean } = {}) {
    try {
      const me = await getCurrentUser();
      setCurrentUser(me);
      if (!me.permissions.includes("super_admin")) {
        setUsers([]);
        if (clearMessage) {
          setMessage("只读模式：仅权限管理员可编辑用户、权限和系统设置。");
        }
        return;
      }
      const [userRows, settings] = await Promise.all([
        listUsers({ keyword, permission: permissionFilter, status: statusFilter }),
        getSystemSettings()
      ]);
      setUsers(userRows.items);
      setAutoCheckEnabled(Boolean(settings.auto_check_enabled));
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

  function startEdit(user: User) {
    setEditingUserId(user.id);
    setForm({
      uid: user.uid,
      name: user.name,
      email: user.email || "",
      status: user.status,
      permissions: user.permissions
    });
  }

  function isCurrentUser(user: User) {
    return currentUser?.id === user.id;
  }

  async function handleSaveUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageAccounts) {
      setMessage("只读模式：仅权限管理员可编辑用户和权限。");
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
      resetForm();
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存账号失败");
    }
  }

  async function handleToggleStatus(user: User) {
    if (!canManageAccounts) {
      setMessage("只读模式：仅权限管理员可编辑用户和权限。");
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
      setMessage("只读模式：仅权限管理员可编辑用户和权限。");
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
        resetForm();
      }
      await refresh({ clearMessage: false });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除账号失败");
    }
  }

  async function handleSaveSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageAccounts) {
      setMessage("只读模式：仅权限管理员可保存系统设置。");
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
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">后台管理</p>
        <h1>用户与权限 / 系统设置</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      {!canManageAccounts ? <p className="notice">只读模式：仅权限管理员可编辑用户、权限和系统设置。</p> : null}

      <section className="admin-layout">
        <nav className="admin-nav" aria-label="后台分区">
          <a href="#accounts">用户与权限</a>
          <a href="#settings">系统设置</a>
        </nav>

        <div className="admin-main">
          <form id="accounts" className="form-panel" onSubmit={handleSaveUser}>
          <h2>{editingUserId ? `编辑账号 · ${form.uid}` : "添加用户"}</h2>
          <label>
            UID
            <input
              name="uid"
              value={form.uid}
              onChange={(event) => updateFormField("uid", event.target.value)}
              disabled={Boolean(editingUserId) || !canManageAccounts}
              required
            />
          </label>
          <label>
            姓名
            <input
              name="name"
              value={form.name}
              onChange={(event) => updateFormField("name", event.target.value)}
              disabled={!canManageAccounts}
              required
            />
          </label>
          <label>
            公司邮箱
            <input
              name="email"
              value={form.email}
              onChange={(event) => updateFormField("email", event.target.value)}
              disabled={!canManageAccounts}
            />
          </label>
          <fieldset className="checkbox-group">
            <legend>用户权限</legend>
            {permissionOptions.map((permission) => (
              <label className="inline" key={permission.key}>
                <input
                  type="checkbox"
                  checked={form.permissions.includes(permission.key)}
                  onChange={() => togglePermission(permission.key)}
                  disabled={!canManageAccounts || (isEditingCurrentUser && permission.key === "super_admin")}
                />
                {permission.label}
              </label>
            ))}
          </fieldset>
          <label>
            状态
            <select
              name="status"
              value={form.status}
              onChange={(event) => updateFormField("status", event.target.value)}
              disabled={!canManageAccounts || isEditingCurrentUser}
            >
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
          </label>
          <div className="button-row">
            <button type="submit" disabled={!canManageAccounts}>
              {editingUserId ? "完成" : "保存账号"}
            </button>
            {editingUserId ? (
              <button className="secondary-button" type="button" onClick={resetForm}>
                取消
              </button>
            ) : null}
          </div>
        </form>

        <form id="settings" className="form-panel" onSubmit={handleSaveSetting}>
          <h2>系统设置</h2>
          <label className="inline">
            <input
              type="checkbox"
              checked={autoCheckEnabled}
              onChange={(event) => setAutoCheckEnabled(event.target.checked)}
              disabled={!canManageAccounts}
            />
            启用自动检查
          </label>
          <button type="submit" disabled={!canManageAccounts}>
            保存设置
          </button>
        </form>

      <section className="module spaced">
        <div className="section-heading">
          <div>
            <h2>账号列表</h2>
            <p>共 {users.length} 个账号 · 启用 {activeCount} 个</p>
          </div>
          <div className="filters">
            <input
              aria-label="搜索 UID、姓名、邮箱"
              placeholder="搜索 UID / 姓名 / 邮箱"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <select
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
            <select aria-label="状态筛选" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">全部状态</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
          </div>
        </div>
        <table>
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
            {users.map((item) => (
              <tr key={item.id}>
                <td>{item.uid}</td>
                <td>{item.name}</td>
                <td>{item.email || "-"}</td>
                <td>{item.permissions.map((permission) => permissionOptions.find((option) => option.key === permission)?.label || permission).join(" / ")}</td>
                <td>{statusLabels[item.status] || item.status}</td>
                <td>
                  <div className="button-row">
                    <button className="secondary-button" type="button" onClick={() => startEdit(item)} disabled={!canManageAccounts}>
                      编辑
                    </button>
                    <button className="secondary-button" type="button" onClick={() => handleToggleStatus(item)} disabled={!canManageAccounts || isCurrentUser(item)}>
                      {item.status === "active" ? "停用" : "启用"}
                    </button>
                    <button className="danger-button" type="button" onClick={() => handleDelete(item)} disabled={!canManageAccounts || isCurrentUser(item)}>
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
        </div>

      <aside className="module spaced">
        <h2>权限说明</h2>
        <div className="permission-grid">
          {permissionOptions.map((permission) => (
            <div key={permission.key}>
              <strong>{permission.label}</strong>
              <p>{permission.description}</p>
            </div>
          ))}
        </div>
      </aside>
      </section>
    </main>
  );
}
