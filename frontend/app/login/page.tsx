"use client";

import { FormEvent, useEffect, useState } from "react";
import { getCurrentUser, login, type User } from "@/lib/api";
import { clearSession, getStoredUser, saveSession } from "@/lib/session";

export default function LoginPage() {
  const [uid, setUid] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [user, setUser] = useState<User | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const result = await login(uid, password);
      saveSession(result);
      setUser(result.user);
      setMessage("登录成功，已保存当前会话。");
      await getCurrentUser();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setMessage("已退出登录。");
  }

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">认证</p>
        <h1>UID 登录</h1>
      </header>
      <section className="two-column">
        <form className="form-panel" onSubmit={handleLogin}>
          <label>
            UID
            <input name="uid" value={uid} onChange={(event) => setUid(event.target.value)} />
          </label>
          <label>
            密码
            <input
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </button>
          {message ? <p className="notice">{message}</p> : null}
        </form>
        <section className="module">
          <h2>当前会话</h2>
          {user ? (
            <div className="stack">
              <p>
                {user.name}（{user.uid}）
              </p>
              <p>权限：{user.permissions.join(" / ")}</p>
              <a className="module-link" href="/">
                返回首页
              </a>
              <button className="secondary-button" type="button" onClick={handleLogout}>
                退出登录
              </button>
            </div>
          ) : (
            <p>未登录。默认种子账号为 admin / admin。</p>
          )}
        </section>
      </section>
    </main>
  );
}
