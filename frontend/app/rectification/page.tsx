export default function RectificationPage() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">整改</p>
        <h1>整改与复查</h1>
      </header>
      <section className="two-column">
        <form className="form-panel">
          <h2>整改项</h2>
          <label>
            任务 ID
            <input name="task_id" />
          </label>
          <button type="button">查询整改项</button>
          <button type="button">标记完成</button>
        </form>
        <form className="form-panel">
          <h2>触发复查</h2>
          <p>所有整改项完成后，创建下一轮，只复查上一轮不满足项。</p>
          <button type="button">触发复查</button>
        </form>
      </section>
    </main>
  );
}
