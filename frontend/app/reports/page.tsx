export default function ReportsPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">报告</p>
        <h1>检查档案</h1>
      </header>
      <form className="form-panel filters">
        <label>
          项目 ID
          <input name="project_id" />
        </label>
        <label>
          QG 节点
          <input name="qg_node_id" />
        </label>
        <label>
          结论
          <select name="overall_result">
            <option value="">全部</option>
            <option value="FULL_GO">FULL_GO</option>
            <option value="C_GO">C_GO</option>
            <option value="NO_GO">NO_GO</option>
          </select>
        </label>
        <button type="button">查询报告</button>
      </form>
      <section className="module">
        <h2>报告详情</h2>
        <p>报告详情展示项目、QG 节点、规则快照、综合结论和多轮过程记录。</p>
      </section>
    </main>
  );
}
