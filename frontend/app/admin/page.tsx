"use client";

import { FormEvent, useEffect, useState } from "react";
import { createUser, getSystemSettings, listUsers, saveSystemSetting, type User } from "@/lib/api";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [uid, setUid] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [permission, setPermission] = useState("inspection_engineer");
  const [autoCheckEnabled, setAutoCheckEnabled] = useState(true);
  const [message, setMessage] = useState("");

  async function refresh() {
    try {
      const [userRows, settings] = await Promise.all([listUsers(), getSystemSettings()]);
      setUsers(userRows.items);
      setAutoCheckEnabled(Boolean(settings.auto_check_enabled));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "后台数据加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await createUser({ uid, name, email, permissions: [permission] });
      setUid("");
      setName("");
      setEmail("");
      setMessage("账号已保存。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存账号失败");
    }
  }

  async function handleSaveSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await saveSystemSetting("auto_check_enabled", autoCheckEnabled);
      setMessage("系统设置已保存。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存设置失败");
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">后台</p>
        <h1>账号权限与系统设置</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <section className="two-column">
        <form className="form-panel" onSubmit={handleCreateUser}>
          <h2>账号维护</h2>
          <label>
            UID
            <input name="uid" value={uid} onChange={(event) => setUid(event.target.value)} required />
          </label>
          <label>
            姓名
            <input name="name" value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            邮箱
            <input name="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            权限
            <select name="permission" value={permission} onChange={(event) => setPermission(event.target.value)}>
              <option value="inspection_engineer">点检工程师</option>
              <option value="rules_admin">规则管理员</option>
              <option value="project_admin">项目管理员</option>
              <option value="super_admin">超级管理员</option>
            </select>
          </label>
          <button type="submit">保存账号</button>
        </form>
        <form className="form-panel" onSubmit={handleSaveSetting}>
          <h2>系统设置</h2>
          <label className="inline">
            <input
              type="checkbox"
              checked={autoCheckEnabled}
              onChange={(event) => setAutoCheckEnabled(event.target.checked)}
            />
            启用自动检查
          </label>
          <button type="submit">保存设置</button>
        </form>
      </section>
      <section className="module spaced">
        <h2>账号列表</h2>
        <table>
          <thead>
            <tr>
              <th>UID</th>
              <th>姓名</th>
              <th>状态</th>
              <th>权限</th>
            </tr>
          </thead>
          <tbody>
            {users.map((item) => (
              <tr key={item.id}>
                <td>{item.uid}</td>
                <td>{item.name}</td>
                <td>{item.status}</td>
                <td>{item.permissions.join(" / ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
