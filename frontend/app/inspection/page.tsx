export default function InspectionPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">点检</p>
        <h1>点检执行</h1>
      </header>
      <section className="summary">
        <div>
          <span>1</span>
          <strong>创建任务</strong>
          <p>选择 normal 项目和已发布 QG 规则。</p>
        </div>
        <div>
          <span>2</span>
          <strong>确认检查项</strong>
          <p>工程师提交 pass、fail、conditional 或 na。</p>
        </div>
        <div>
          <span>3</span>
          <strong>归档当前轮</strong>
          <p>所有检查项确认后计算节点结论。</p>
        </div>
        <div>
          <span>4</span>
          <strong>作废任务</strong>
          <p>误建任务保留历史并禁用后续动作。</p>
        </div>
      </section>
      <form className="form-panel">
        <h2>新建点检任务</h2>
        <label>
          项目 ID
          <input name="project_id" />
        </label>
        <label>
          QG 节点 ID
          <input name="qg_node_id" />
        </label>
        <button type="button">创建任务</button>
      </form>
    </main>
  );
}
