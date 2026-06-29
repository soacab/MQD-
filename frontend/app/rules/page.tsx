"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  createBusinessRule,
  createExecutionRule,
  createRuleVersion,
  getRuleVersion,
  listQGNodes,
  listRuleVersions,
  publishRuleVersion,
  type QGNode,
  type RuleVersion
} from "@/lib/api";

export default function RulesPage() {
  const [nodes, setNodes] = useState<QGNode[]>([]);
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<RuleVersion | null>(null);
  const [message, setMessage] = useState("");
  const [versionForm, setVersionForm] = useState({ qg_node_id: "1", version_no: "V01", change_summary: "P0 演示规则" });
  const [ruleForm, setRuleForm] = useState({
    rule_code: "P0_MANUAL",
    item_name: "P0 人工检查项",
    item_type: "manual",
    check_type: "manual",
    checklist_requirement: "工程师确认检查结论",
    owner_dept: "MQD"
  });

  async function refresh(qgNodeId = Number(versionForm.qg_node_id)) {
    try {
      const [nodeRows, versionRows] = await Promise.all([listQGNodes(), listRuleVersions(qgNodeId)]);
      setNodes(nodeRows.items);
      setVersions(versionRows.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "规则数据加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreateVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const version = await createRuleVersion({
        qg_node_id: Number(versionForm.qg_node_id),
        version_no: versionForm.version_no,
        change_summary: versionForm.change_summary
      });
      setSelectedVersion(version);
      setMessage("草稿版本已创建。");
      await refresh(version.qg_node_id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建草稿失败");
    }
  }

  async function handleSelectVersion(versionId: number) {
    try {
      setSelectedVersion(await getRuleVersion(versionId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "版本详情加载失败");
    }
  }

  async function handleCreateRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedVersion) {
      setMessage("请先选择或创建草稿版本。");
      return;
    }
    try {
      const rule = await createBusinessRule(selectedVersion.id, {
        ...ruleForm,
        sort_order: selectedVersion.business_check_rules?.length || 0,
        is_active: true,
        is_apqp: false
      });
      if (rule.item_type === "auto" || rule.item_type === "system") {
        await createExecutionRule(rule.id, {
          execution_code: `${rule.rule_code}_EXEC`,
          execution_mode: rule.item_type === "system" ? "system_direct" : "file_existence",
          adapter_type: rule.item_type === "system" ? "mock_system" : "vdrive",
          config_version: "V1",
          is_enabled: true,
          config_json: { mock: true }
        });
      }
      setMessage("检查项已保存。");
      await handleSelectVersion(selectedVersion.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存检查项失败");
    }
  }

  async function handlePublish() {
    if (!selectedVersion) {
      return;
    }
    try {
      const version = await publishRuleVersion(selectedVersion.id);
      setSelectedVersion(version);
      setMessage("规则版本已发布。");
      await refresh(version.qg_node_id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布失败");
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">规则</p>
        <h1>规则配置与版本发布</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <section className="two-column">
        <form className="form-panel" onSubmit={handleCreateVersion}>
          <h2>规则版本</h2>
          <label>
            QG 节点
            <select
              name="qg_node_id"
              value={versionForm.qg_node_id}
              onChange={(event) => setVersionForm({ ...versionForm, qg_node_id: event.target.value })}
            >
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.node_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            版本号
            <input
              name="version_no"
              value={versionForm.version_no}
              onChange={(event) => setVersionForm({ ...versionForm, version_no: event.target.value })}
            />
          </label>
          <label>
            变更说明
            <input
              name="change_summary"
              value={versionForm.change_summary}
              onChange={(event) => setVersionForm({ ...versionForm, change_summary: event.target.value })}
            />
          </label>
          <button type="submit">创建草稿</button>
        </form>
        <form className="form-panel" onSubmit={handleCreateRule}>
          <h2>检查项</h2>
          <label>
            检查项编码
            <input
              name="rule_code"
              value={ruleForm.rule_code}
              onChange={(event) => setRuleForm({ ...ruleForm, rule_code: event.target.value })}
            />
          </label>
          <label>
            检查项名称
            <input
              name="item_name"
              value={ruleForm.item_name}
              onChange={(event) => setRuleForm({ ...ruleForm, item_name: event.target.value })}
            />
          </label>
          <label>
            类型
            <select
              name="item_type"
              value={ruleForm.item_type}
              onChange={(event) => setRuleForm({ ...ruleForm, item_type: event.target.value, check_type: event.target.value })}
            >
              <option value="manual">人工</option>
              <option value="auto">自动</option>
              <option value="system">系统直连</option>
              <option value="inherit">继承</option>
            </select>
          </label>
          <label>
            Checklist 要求
            <input
              value={ruleForm.checklist_requirement}
              onChange={(event) => setRuleForm({ ...ruleForm, checklist_requirement: event.target.value })}
            />
          </label>
          <button type="submit">保存检查项</button>
        </form>
      </section>
      <section className="two-column spaced">
        <section className="module">
          <h2>版本列表</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>版本</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id} onClick={() => void handleSelectVersion(version.id)}>
                  <td>{version.id}</td>
                  <td>{version.version_no}</td>
                  <td>{version.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="module">
          <h2>版本详情</h2>
          {selectedVersion ? (
            <div className="stack">
              <p>
                {selectedVersion.version_no}，状态：{selectedVersion.status}
              </p>
              <button type="button" disabled={selectedVersion.status !== "draft"} onClick={handlePublish}>
                发布规则版本
              </button>
              <ul className="plain-list">
                {selectedVersion.business_check_rules?.map((rule) => (
                  <li key={rule.id}>
                    {rule.rule_code}：{rule.item_name}（{rule.item_type}）
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p>请选择一个规则版本。</p>
          )}
        </section>
      </section>
    </main>
  );
}
