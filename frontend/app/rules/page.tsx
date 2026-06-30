"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  createBusinessRule,
  createExecutionRule,
  createRuleVersion,
  getCurrentUser,
  getRuleVersion,
  listQGNodes,
  listRuleVersions,
  publishRuleVersion,
  updateBusinessRule,
  type BusinessRule,
  type QGNode,
  type RuleVersion,
  type User
} from "@/lib/api";

export default function RulesPage() {
  const [nodes, setNodes] = useState<QGNode[]>([]);
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<RuleVersion | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
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
  const canManageRules = Boolean(currentUser?.permissions.includes("rules_admin"));

  async function refresh(qgNodeId = Number(versionForm.qg_node_id)) {
    try {
      const [me, nodeRows, versionRows] = await Promise.all([getCurrentUser(), listQGNodes(), listRuleVersions(qgNodeId)]);
      setCurrentUser(me);
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
      if (!canManageRules) {
        setMessage("只读模式：规则管理员可编辑，其他用户只能查看。");
        return;
      }
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
      setEditingRuleId(null);
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
    if (!canManageRules) {
      setMessage("只读模式：规则管理员可编辑，其他用户只能查看。");
      return;
    }
    if (selectedVersion.status !== "draft") {
      setMessage("只读模式：已发布或已废弃版本不可编辑。");
      return;
    }
    try {
      const editablePayload = { ...ruleForm };
      const createPayload = {
        ...editablePayload,
        sort_order: selectedVersion.business_check_rules?.length || 0,
        is_active: true,
        is_apqp: false
      };
      const rule = editingRuleId
        ? await updateBusinessRule(editingRuleId, editablePayload)
        : await createBusinessRule(selectedVersion.id, createPayload);
      if (!editingRuleId && (rule.item_type === "auto" || rule.item_type === "system")) {
        await createExecutionRule(rule.id, {
          execution_code: `${rule.rule_code}_EXEC`,
          execution_mode: rule.item_type === "system" ? "system_direct" : "file_existence",
          adapter_type: rule.item_type === "system" ? "mock_system" : "vdrive",
          config_version: "V1",
          is_enabled: true,
          config_json: { mock: true }
        });
      }
      setEditingRuleId(null);
      setMessage(editingRuleId ? "检查项已更新。" : "检查项已保存。");
      await handleSelectVersion(selectedVersion.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存检查项失败");
    }
  }

  async function handlePublish() {
    if (!selectedVersion) {
      return;
    }
    if (!canManageRules) {
      setMessage("只读模式：规则管理员可发布版本。");
      return;
    }
    const confirmed = window.confirm(`发布前确认\n\n版本：${selectedVersion.version_no}\n变更说明：${selectedVersion.change_summary || "无"}\n\n发布后该版本将不可编辑。`);
    if (!confirmed) {
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

  function startEditRule(rule: BusinessRule) {
    setEditingRuleId(rule.id);
    setRuleForm({
      rule_code: rule.rule_code,
      item_name: rule.item_name,
      item_type: rule.item_type,
      check_type: rule.check_type,
      checklist_requirement: rule.checklist_requirement || "",
      owner_dept: rule.owner_dept || ""
    });
  }

  const groupedRules = {
    manual: selectedVersion?.business_check_rules?.filter((rule) => rule.item_type === "manual" || rule.item_type === "inherit") || [],
    auto: selectedVersion?.business_check_rules?.filter((rule) => rule.item_type === "auto" || rule.item_type === "system") || []
  };

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">规则</p>
        <h1>规则配置与版本发布</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      {!canManageRules ? <p className="notice">只读模式：规则管理员可编辑，当前用户只能查看版本历史和检查项。</p> : null}
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
          <button type="submit" disabled={!canManageRules}>创建草稿</button>
        </form>
        <form className="form-panel" onSubmit={handleCreateRule}>
          <h2>{editingRuleId ? "编辑检查项" : "检查项"}</h2>
          <p>规则管理员可编辑；点检执行和项目管理权限用户进入只读模式。</p>
          <label>
            检查项编码
            <input
              name="rule_code"
              value={ruleForm.rule_code}
              onChange={(event) => setRuleForm({ ...ruleForm, rule_code: event.target.value })}
              disabled={Boolean(editingRuleId) || !canManageRules}
            />
          </label>
          <label>
            检查项名称
            <input
              name="item_name"
              value={ruleForm.item_name}
              onChange={(event) => setRuleForm({ ...ruleForm, item_name: event.target.value })}
              disabled={!canManageRules}
            />
          </label>
          <label>
            类型
            <select
              name="item_type"
              value={ruleForm.item_type}
              onChange={(event) => setRuleForm({ ...ruleForm, item_type: event.target.value, check_type: event.target.value })}
              disabled={!canManageRules}
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
              disabled={!canManageRules}
            />
          </label>
          <label>
            责任方
            <input
              value={ruleForm.owner_dept}
              onChange={(event) => setRuleForm({ ...ruleForm, owner_dept: event.target.value })}
              disabled={!canManageRules}
            />
          </label>
          <button type="submit" disabled={!canManageRules || selectedVersion?.status !== "draft"}>{editingRuleId ? "更新检查项" : "保存检查项"}</button>
        </form>
      </section>
      <section className="two-column spaced">
        <section className="module">
          <h2>版本历史</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>版本</th>
                <th>状态</th>
                <th>变更说明</th>
                <th>发布时间</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id} onClick={() => void handleSelectVersion(version.id)}>
                  <td>{version.id}</td>
                  <td>{version.version_no}</td>
                  <td>{version.status}</td>
                  <td>{version.change_summary || "-"}</td>
                  <td>{version.published_at || "-"}</td>
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
              <p>发布前确认：{selectedVersion.change_summary || "未填写变更说明"}</p>
              <h3>人工检查项</h3>
              <ul className="plain-list">
                {groupedRules.manual.map((rule) => (
                  <li key={rule.id}>
                    <button className="link-button" type="button" onClick={() => startEditRule(rule)}>
                      {rule.rule_code}：{rule.item_name}（{rule.item_type}）
                    </button>
                  </li>
                ))}
              </ul>
              <h3>自动检查项</h3>
              <ul className="plain-list">
                {groupedRules.auto.map((rule) => (
                  <li key={rule.id}>
                    <button className="link-button" type="button" onClick={() => startEditRule(rule)}>
                      {rule.rule_code}：{rule.item_name}（{rule.item_type}）
                    </button>
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
