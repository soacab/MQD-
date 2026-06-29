export default function LoginPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">认证</p>
        <h1>UID 登录</h1>
      </header>
      <form className="form-panel">
        <label>
          UID
          <input name="uid" defaultValue="admin" />
        </label>
        <label>
          密码
          <input name="password" type="password" defaultValue="admin" />
        </label>
        <button type="button">登录</button>
      </form>
    </main>
  );
}
