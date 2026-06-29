import { fetchHealth } from "@/lib/api";

const modules = [
  ["项目", "项目创建、VDrive 链接、加单、软删除"],
  ["规则", "QG 节点、规则版本、检查项、执行规则发布"],
  ["点检", "任务创建、规则快照、首轮检查项、工程师确认"],
  ["归档", "FULL_GO / C_GO / NO_GO 结论、报告和过程记录"],
  ["整改", "整改项、待跟进项、复查轮次"],
  ["后台", "账号权限、系统设置、审计日志"]
];

export default async function Page() {
  const health = await fetchHealth();

  return (
    <main className="shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">MQD 点检</p>
          <h1>CheckFlow</h1>
        </div>
        <nav aria-label="主导航">
          {modules.map(([title]) => (
            <a key={title} href={`#${title}`}>
              {title}
            </a>
          ))}
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">P0 主流程工作台</p>
            <h2>项目到复查的最小闭环</h2>
          </div>
          <div className={health.reachable ? "status ok" : "status warn"}>
            后端 /health: {health.status}
          </div>
        </header>

        <section className="summary">
          <div>
            <span>1</span>
            <strong>创建项目</strong>
            <p>保存项目上下文和 VDrive 文件夹标识。</p>
          </div>
          <div>
            <span>2</span>
            <strong>发布规则</strong>
            <p>冻结业务规则和自动执行规则。</p>
          </div>
          <div>
            <span>3</span>
            <strong>执行点检</strong>
            <p>生成检查项，工程师确认最终结论。</p>
          </div>
          <div>
            <span>4</span>
            <strong>归档复查</strong>
            <p>生成报告、整改项和下一轮复查。</p>
          </div>
        </section>

        <section className="grid" aria-label="模块入口">
          {modules.map(([title, description]) => (
            <article id={title} key={title} className="module">
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
