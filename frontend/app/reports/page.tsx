"use client";

import { FormEvent, useEffect, useState } from "react";
import { getReport, listReports, type Report } from "@/lib/api";

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [message, setMessage] = useState("");
  const [filters, setFilters] = useState({ project_id: "", qg_node_id: "", overall_result: "" });

  async function refresh() {
    try {
      const rows = await listReports(filters);
      setReports(rows.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告列表加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await refresh();
  }

  async function handleSelect(reportId: number) {
    try {
      setSelectedReport(await getReport(reportId));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告详情加载失败");
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">报告</p>
        <h1>检查档案</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <form className="form-panel filters" onSubmit={handleSearch}>
        <label>
          项目 ID
          <input
            name="project_id"
            value={filters.project_id}
            onChange={(event) => setFilters({ ...filters, project_id: event.target.value })}
          />
        </label>
        <label>
          QG 节点
          <input
            name="qg_node_id"
            value={filters.qg_node_id}
            onChange={(event) => setFilters({ ...filters, qg_node_id: event.target.value })}
          />
        </label>
        <label>
          结论
          <select
            name="overall_result"
            value={filters.overall_result}
            onChange={(event) => setFilters({ ...filters, overall_result: event.target.value })}
          >
            <option value="">全部</option>
            <option value="FULL_GO">FULL_GO</option>
            <option value="C_GO">C_GO</option>
            <option value="NO_GO">NO_GO</option>
          </select>
        </label>
        <button type="submit">查询报告</button>
      </form>
      <section className="two-column">
        <section className="module">
          <h2>报告列表</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>报告号</th>
                <th>结论</th>
                <th>轮次</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id} onClick={() => void handleSelect(report.id)}>
                  <td>{report.id}</td>
                  <td>{report.report_no}</td>
                  <td>{report.overall_result || "未归档"}</td>
                  <td>{report.latest_round_no}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="module">
          <h2>报告详情</h2>
          {selectedReport ? (
            <div className="stack">
              <p>项目：{selectedReport.project?.project_name || selectedReport.project_id}</p>
              <p>QG 节点：{selectedReport.qg_node?.node_name || selectedReport.qg_node_id}</p>
              <p>综合结论：{selectedReport.overall_result || "未归档"}</p>
              <p>规则版本：{selectedReport.business_rule_version_no}</p>
              <p>规则快照项数：{selectedReport.rule_snapshot?.business_rule_snapshot_json?.length || 0}</p>
              <table>
                <thead>
                  <tr>
                    <th>检查项</th>
                    <th>结论</th>
                    <th>过程记录</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedReport.items?.map((item) => (
                    <tr key={item.id}>
                      <td>{item.item_name_snapshot}</td>
                      <td>{item.final_result}</td>
                      <td>{item.process_records_json.length} 条</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>请选择报告。</p>
          )}
        </section>
      </section>
    </main>
  );
}
