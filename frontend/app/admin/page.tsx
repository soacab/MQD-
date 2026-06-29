export default function AdminPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">后台</p>
        <h1>账号权限与系统设置</h1>
      </header>
      <section className="two-column">
        <form className="form-panel">
          <h2>账号维护</h2>
          <label>
            UID
            <input name="uid" />
          </label>
          <label>
            姓名
            <input name="name" />
          </label>
          <label>
            权限
            <select name="permission" defaultValue="inspection_engineer">
              <option value="inspection_engineer">点检工程师</option>
              <option value="rules_admin">规则管理员</option>
              <option value="project_admin">项目管理员</option>
              <option value="super_admin">超级管理员</option>
            </select>
          </label>
          <button type="button">保存账号</button>
        </form>
        <form className="form-panel">
          <h2>系统设置</h2>
          <label className="inline">
            <input type="checkbox" defaultChecked />
            启用自动检查
          </label>
          <button type="button">保存设置</button>
        </form>
      </section>
    </main>
  );
}
