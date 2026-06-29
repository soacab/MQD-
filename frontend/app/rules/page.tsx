export default function RulesPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">规则</p>
        <h1>规则配置与版本发布</h1>
      </header>
      <section className="two-column">
        <form className="form-panel">
          <h2>规则版本</h2>
          <label>
            QG 节点
            <select name="qg_node_id" defaultValue="1">
              <option value="1">QG2</option>
              <option value="2">QG3.1</option>
              <option value="3">QG3.2</option>
              <option value="4">QG3.3</option>
              <option value="5">QG3</option>
              <option value="6">QG4</option>
            </select>
          </label>
          <label>
            版本号
            <input name="version_no" placeholder="V01" />
          </label>
          <button type="button">创建草稿</button>
        </form>
        <form className="form-panel">
          <h2>检查项</h2>
          <label>
            检查项编码
            <input name="rule_code" />
          </label>
          <label>
            类型
            <select name="item_type" defaultValue="manual">
              <option value="manual">人工</option>
              <option value="auto">自动</option>
              <option value="system">系统直连</option>
              <option value="inherit">继承</option>
            </select>
          </label>
          <button type="button">保存检查项</button>
        </form>
      </section>
    </main>
  );
}
