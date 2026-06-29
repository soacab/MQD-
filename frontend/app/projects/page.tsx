export default function ProjectsPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">项目</p>
        <h1>项目管理</h1>
      </header>
      <section className="two-column">
        <form className="form-panel">
          <h2>创建项目</h2>
          <label>
            项目名称
            <input name="project_name" />
          </label>
          <label>
            客户
            <input name="customer" />
          </label>
          <label>
            VDrive 链接
            <input name="vdrive_url" />
          </label>
          <label>
            接收日期
            <input name="receive_date" type="date" />
          </label>
          <button type="button">校验并创建</button>
        </form>
        <section className="module">
          <h2>项目列表</h2>
          <p>普通列表默认展示 normal 项目；删除项目需输入项目名称确认。</p>
        </section>
      </section>
    </main>
  );
}
