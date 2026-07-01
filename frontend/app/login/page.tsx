"use client";

import { FormEvent, useEffect, useState } from "react";
import { getCurrentUser, login, type User } from "@/lib/api";
import { clearSession, getStoredUser, saveSession } from "@/lib/session";

export default function LoginPage() {
  const [uid, setUid] = useState("UID00001");
  const [password, setPassword] = useState("admin");
  const [rememberIdentity, setRememberIdentity] = useState(true);
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
    <main className="login-shell">
      <section className="login-card" aria-label="登录工作台">
        <form className="login-form" onSubmit={handleLogin}>
          <div className="login-head">
            <h1>登录工作台</h1>
            <p>使用公司 UID 登录 CheckFlow。</p>
          </div>

          <label className="login-field">
            <span>UID</span>
            <input name="uid" value={uid} onChange={(event) => setUid(event.target.value)} />
          </label>

          <label className="login-field">
            <span>密码</span>
            <input
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          <label className="login-remember">
            <input
              type="checkbox"
              checked={rememberIdentity}
              onChange={(event) => setRememberIdentity(event.target.checked)}
            />
            <span>记住本次身份</span>
          </label>

          <button className="login-submit" type="submit" disabled={loading}>
            {loading ? "登录中..." : "登录进入"}
          </button>
        </form>

        {user ? (
          <div className="login-session" aria-label="当前会话">
            <span>
              {user.name} · {user.uid}
            </span>
            <a href="/">进入工作台</a>
            <button type="button" onClick={handleLogout}>
              退出登录
            </button>
          </div>
        ) : null}
      </section>

      {message ? <div className="login-toast" role="status">{message}</div> : null}
    </main>
  );
}
