"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createBusinessRule,
  getRuleReleaseDraft,
  getCurrentUser,
  getRuleVersion,
  listQGNodes,
  listRuleVersions,
  prepareEditableRuleVersion,
  publishRuleReleaseBatch,
  updateBusinessRule,
  type BusinessRule,
  type QGNode,
  type RuleReleaseDraft,
  type RuleVersion,
  type User
} from "@/lib/api";

const emptyRuleForm = {
  item_name: "",
  checklist_requirement: "",
  owner_dept: "MQD",
  is_apqp: "true",
  is_active: "true"
};

const itemTypeLabels: Record<string, string> = {
  manual: "人工",
  auto: "自动",
  system: "系统直连",
  inherit: "继承"
};

const checkTypeLabels: Record<string, string> = {
  manual: "人工确认",
  file_existence: "存在性判断",
  content_check: "内容判断",
  system_direct: "系统直连",
  inherit: "继承"
};

function asBoolean(value: number | boolean | undefined) {
  return value === true || value === 1;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

function versionStatusLabel(status: string) {
  if (status === "draft") {
    return "未发布";
  }
  if (status === "published") {
    return "已发布";
  }
  if (status === "deprecated") {
    return "历史版本";
  }
  return status;
}

function selectPreferredRuleVersion(versions: RuleVersion[], preferredVersionId?: number) {
  return (
    (preferredVersionId ? versions.find((version) => version.id === preferredVersionId) : null) ||
    versions.find((version) => version.is_current) ||
    versions.find((version) => version.status === "published") ||
    versions[0] ||
    null
  );
}

function nodePublishedRuleCounts(nodeRows: QGNode[]) {
  return Object.fromEntries(nodeRows.map((node) => [node.id, node.published_rule_count ?? 0]));
}

function ruleCategoryLabel(itemType?: string | null) {
  if (itemType === "manual") {
    return "人工检查项";
  }
  if (itemType === "auto") {
    return "自动检查项";
  }
  if (itemType === "system") {
    return "系统直连检查项";
  }
  if (itemType === "inherit") {
    return "继承检查项";
  }
  return "检查项";
}

function changeTypeLabel(changeType: string) {
  if (changeType === "disabled") {
    return "禁";
  }
  if (changeType === "added") {
    return "增";
  }
  if (changeType === "modified") {
    return "改";
  }
  if (changeType === "removed") {
    return "删";
  }
  return "变";
}

function formatRuleChangeLine(item: { item_name: string; item_type?: string | null; change_type: string; change_summary?: string | null }) {
  const summary = item.change_summary ? `（${item.change_summary}）` : "";
  return `${changeTypeLabel(item.change_type)} ${ruleCategoryLabel(item.item_type)}：${item.item_name}${summary}`;
}

function formatRuleFieldValue(field: string, value?: string | number | boolean | null) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (field === "item_type") {
    return ruleCategoryLabel(String(value));
  }
  if (field === "check_type") {
    return checkTypeLabels[String(value)] || String(value);
  }
  if (field === "is_apqp") {
    return value === true || value === 1 ? "是" : "否";
  }
  if (field === "is_active") {
    return value === true || value === 1 ? "启用" : "停用";
  }
  return String(value);
}

function formatRuleFieldChangeLine(detail: { field: string; label: string; old_value?: string | number | boolean | null; new_value?: string | number | boolean | null }) {
  return `${detail.label}：${formatRuleFieldValue(detail.field, detail.old_value)} -> ${formatRuleFieldValue(detail.field, detail.new_value)}`;
}

function ruleFormFromRule(rule: BusinessRule) {
  return {
    item_name: rule.item_name,
    checklist_requirement: rule.checklist_requirement || "",
    owner_dept: rule.owner_dept || "",
    is_apqp: asBoolean(rule.is_apqp) ? "true" : "false",
    is_active: asBoolean(rule.is_active) ? "true" : "false"
  };
}

function rulePayloadChanged(rule: BusinessRule, payload: { item_name: string; checklist_requirement: string; owner_dept: string; is_apqp: boolean; is_active: boolean }) {
  return (
    rule.item_name !== payload.item_name ||
    (rule.checklist_requirement || "") !== payload.checklist_requirement ||
    (rule.owner_dept || "") !== payload.owner_dept ||
    asBoolean(rule.is_apqp) !== payload.is_apqp ||
    asBoolean(rule.is_active) !== payload.is_active
  );
}

function rulePatchFromDirtyFields(rule: BusinessRule, payload: { item_name: string; checklist_requirement: string; owner_dept: string; is_apqp: boolean; is_active: boolean }, dirtyFields: string[]) {
  const patch: Record<string, unknown> = {};
  for (const field of dirtyFields) {
    if (field === "item_name" && rule.item_name !== payload.item_name) {
      patch.item_name = payload.item_name;
    }
    if (field === "checklist_requirement" && (rule.checklist_requirement || "") !== payload.checklist_requirement) {
      patch.checklist_requirement = payload.checklist_requirement;
    }
    if (field === "owner_dept" && (rule.owner_dept || "") !== payload.owner_dept) {
      patch.owner_dept = payload.owner_dept;
    }
    if (field === "is_apqp" && asBoolean(rule.is_apqp) !== payload.is_apqp) {
      patch.is_apqp = payload.is_apqp;
    }
    if (field === "is_active" && asBoolean(rule.is_active) !== payload.is_active) {
      patch.is_active = payload.is_active;
    }
  }
  return patch;
}

export default function RulesPage() {
  const [nodes, setNodes] = useState<QGNode[]>([]);
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<RuleVersion | null>(null);
  const [nodeRuleCounts, setNodeRuleCounts] = useState<Record<number, number>>({});
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<"auto" | "manual">("auto");
  const [ruleForm, setRuleForm] = useState(emptyRuleForm);
  const [ruleFormDirtyFields, setRuleFormDirtyFields] = useState<string[]>([]);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [editingRuleSource, setEditingRuleSource] = useState<BusinessRule | null>(null);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [ruleModalReadonly, setRuleModalReadonly] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState<number | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [releaseDraft, setReleaseDraft] = useState<RuleReleaseDraft | null>(null);
  const [publishSummary, setPublishSummary] = useState("");
  const [isPublishing, setIsPublishing] = useState(false);
  const [message, setMessage] = useState("");

  const canManageRules = Boolean(currentUser?.permissions.includes("rules_admin"));
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null;
  const rules = selectedVersion?.business_check_rules || [];
  const autoRules = rules.filter((rule) => rule.item_type === "auto" || rule.item_type === "system");
  const manualRules = rules.filter((rule) => rule.item_type === "manual" || rule.item_type === "inherit");
  const visibleRules = activeTab === "auto" ? autoRules : manualRules;
  const draftVersion = versions.find((version) => version.status === "draft") || null;
  const historyVersions = versions.filter((version) => version.status !== "draft");
  const canSubmitUpgradeSuggestion = editingRuleSource?.item_type === "manual" && Boolean(editingRuleId);
  const selectedNodeHasPublishableDraft = Boolean(
    draftVersion && releaseDraft?.nodes.some((node) => node.qg_node_id === selectedNodeId)
  );

  const selectedVersionMeta = useMemo(() => {
    if (!selectedVersion) {
      return "请选择规则版本";
    }
    if (selectedVersion.status === "draft") {
      return `未发布规则变更 · 共 ${rules.length} 条`;
    }
    return `生效于 ${formatDate(selectedVersion.published_at)} · ${selectedVersion.published_by_name || "-"} · 共 ${rules.length} 条`;
  }, [rules.length, selectedVersion]);

  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent("checkflow:rules-actions-state", {
        detail: {
          canPublish: canManageRules && (releaseDraft === null || Boolean(releaseDraft.has_draft)),
          isPublishing
        }
      })
    );
  }, [canManageRules, releaseDraft, isPublishing]);

  useEffect(() => {
    function openHistoryFromTopbar() {
      setHistoryOpen(true);
    }

    function openPublishFromTopbar() {
      void openPublishModal();
    }

    window.addEventListener("checkflow:rules-open-history", openHistoryFromTopbar);
    window.addEventListener("checkflow:rules-open-publish", openPublishFromTopbar);
    return () => {
      window.removeEventListener("checkflow:rules-open-history", openHistoryFromTopbar);
      window.removeEventListener("checkflow:rules-open-publish", openPublishFromTopbar);
    };
  }, [canManageRules, releaseDraft, isPublishing, selectedVersion]);

  async function refreshRuleReleaseDraft(canReadDraft = canManageRules) {
    if (!canReadDraft) {
      setReleaseDraft(null);
      return null;
    }
    const draft = await getRuleReleaseDraft();
    setReleaseDraft(draft);
    return draft;
  }

  async function loadNode(qgNodeId: number, preferredVersionId?: number) {
    const versionRows = await listRuleVersions(qgNodeId);
    setVersions(versionRows.items);
    const preferred = selectPreferredRuleVersion(versionRows.items, preferredVersionId);
    if (preferred) {
      const detail = await getRuleVersion(preferred.id);
      setSelectedVersion(detail);
      if (detail.status === "published" && detail.is_current) {
        const publishedRuleCount = detail.business_check_rules?.length || 0;
        setNodeRuleCounts((current) => ({
          ...current,
          [qgNodeId]: publishedRuleCount
        }));
        setNodes((current) =>
          current.map((node) => (node.id === qgNodeId ? { ...node, published_rule_count: publishedRuleCount } : node))
        );
      }
    } else {
      setSelectedVersion(null);
      setNodeRuleCounts((current) => ({ ...current, [qgNodeId]: 0 }));
    }
  }

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [me, nodeRows] = await Promise.all([getCurrentUser(), listQGNodes()]);
        setCurrentUser(me);
        setNodes(nodeRows.items);
        setNodeRuleCounts(nodePublishedRuleCounts(nodeRows.items));
        if (me.permissions.includes("rules_admin")) {
          await refreshRuleReleaseDraft(true);
        }
        const firstNodeId = nodeRows.items[0]?.id ?? null;
        setSelectedNodeId(firstNodeId);
        if (firstNodeId) {
          await loadNode(firstNodeId);
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "规则数据加载失败");
      }
    }
    void loadInitialData();
  }, []);

  async function handleSelectNode(qgNodeId: number) {
    try {
      setSelectedNodeId(qgNodeId);
      setActiveTab("auto");
      setExpandedHistoryId(null);
      await loadNode(qgNodeId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "规则版本加载失败");
    }
  }

  async function ensureEditableVersion(rule?: BusinessRule) {
    if (!selectedNodeId) {
      throw new Error("请先选择 QG 节点。");
    }
    if (selectedVersion?.status === "draft") {
      return { version: selectedVersion, rule };
    }
    const draft = await prepareEditableRuleVersion(selectedNodeId);
    setSelectedVersion(draft);
    const versionRows = await listRuleVersions(selectedNodeId);
    setVersions(versionRows.items);
    await refreshRuleReleaseDraft(true);
    const copiedRule = rule ? draft.business_check_rules?.find((item) => item.rule_code === rule.rule_code) : undefined;
    setMessage("已准备可编辑规则版本，保存后发布规则版本才会影响新建任务。");
    return { version: draft, rule: copiedRule };
  }

  async function openPublishModal() {
    if (!canManageRules || isPublishing) {
      return;
    }
    try {
      const draft = await refreshRuleReleaseDraft(true);
      if (!draft?.has_draft) {
        setMessage("当前没有可发布的规则变更。");
        return;
      }
      setPublishOpen(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布批次草稿加载失败");
    }
  }

  function openCreateRuleModal() {
    if (!canManageRules) {
      setMessage("仅规则管理员可编辑，其他用户只能查看。");
      return;
    }
    setEditingRuleId(null);
    setEditingRuleSource(null);
    setRuleModalReadonly(false);
    setRuleForm(emptyRuleForm);
    setRuleFormDirtyFields([]);
    setRuleModalOpen(true);
  }

  function openRuleModal(rule: BusinessRule) {
    if (!canManageRules) {
      setEditingRuleId(rule.id);
      setEditingRuleSource(rule);
      setRuleModalReadonly(true);
      setRuleForm(ruleFormFromRule(rule));
      setRuleFormDirtyFields([]);
      setRuleModalOpen(true);
      return;
    }
    setEditingRuleId(rule.id);
    setEditingRuleSource(rule);
    setRuleModalReadonly(false);
    setRuleForm(ruleFormFromRule(rule));
    setRuleFormDirtyFields([]);
    setRuleModalOpen(true);
  }

  function updateRuleFormField(field: keyof typeof emptyRuleForm, value: string) {
    setRuleForm((current) => ({ ...current, [field]: value }));
    setRuleFormDirtyFields((current) => (current.includes(field) ? current : [...current, field]));
  }

  async function handleSaveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedVersion) {
      setMessage("请先选择 QG 节点。");
      return;
    }
    if (!canManageRules) {
      setMessage("仅规则管理员可编辑，其他用户只能查看。");
      return;
    }
    try {
      const payload = {
        item_name: ruleForm.item_name,
        checklist_requirement: ruleForm.checklist_requirement,
        owner_dept: ruleForm.owner_dept,
        is_apqp: ruleForm.is_apqp === "true",
        is_active: ruleForm.is_active === "true"
      };
      const wasCreating = !editingRuleId;
      let dirtyPayload: Record<string, unknown> = {};
      if (editingRuleId) {
        if (!editingRuleSource) {
          setMessage("未找到待编辑检查项。");
          return;
        }
        dirtyPayload = rulePatchFromDirtyFields(editingRuleSource, payload, ruleFormDirtyFields);
        if (!ruleFormDirtyFields.length || !Object.keys(dirtyPayload).length || !rulePayloadChanged(editingRuleSource, payload)) {
          closeRuleModal();
          setMessage("未检测到字段变化，无需发布规则版本。");
          return;
        }
      }
      const editable = editingRuleId
        ? await ensureEditableVersion(editingRuleSource || undefined)
        : await ensureEditableVersion();
      if (editingRuleId) {
        const targetRule = editable.rule || editingRuleSource;
        if (!targetRule) {
          setMessage("未找到待编辑检查项。");
          return;
        }
        await updateBusinessRule(targetRule.id, dirtyPayload);
      } else {
        await createBusinessRule(editable.version.id, payload);
      }
      if (wasCreating) {
        setActiveTab("manual");
      }
      closeRuleModal();
      setMessage(wasCreating ? "新增人工检查项已保存到未发布草稿。" : "检查项修改已保存到未发布草稿。");
      await loadNode(editable.version.qg_node_id, editable.version.id);
      await refreshRuleReleaseDraft(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存检查项失败");
    }
  }

  function openUpgradeSuggestion() {
    setMessage("人工检查项升级建议入口已保留，建议内容持久化将在后续功能中接入。");
  }

  async function stopManualRule(rule: BusinessRule) {
    if (!canManageRules) {
      setMessage("仅规则管理员可删除人工检查项。");
      return;
    }
    if (rule.item_type !== "manual") {
      setMessage("自动检查项不可删除；可通过启用状态控制是否进入新任务。");
      return;
    }
    try {
      const editable = await ensureEditableVersion(rule);
      const targetRule = editable.rule || rule;
      await updateBusinessRule(targetRule.id, { is_active: false });
      closeRuleModal();
      setMessage("删除检查项已保存到未发布规则变更。");
      await loadNode(editable.version.qg_node_id, editable.version.id);
      await refreshRuleReleaseDraft(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除人工检查项失败");
    }
  }

  function closeRuleModal() {
    setRuleModalOpen(false);
    setEditingRuleId(null);
    setEditingRuleSource(null);
    setRuleFormDirtyFields([]);
  }

  async function confirmPublish() {
    if (isPublishing) {
      return;
    }
    if (!releaseDraft?.has_draft) {
      setMessage("当前没有可发布的规则变更。");
      setPublishOpen(false);
      return;
    }
    try {
      setIsPublishing(true);
      const trimmedSummary = publishSummary.trim();
      const batch = await publishRuleReleaseBatch(trimmedSummary ? { change_summary: trimmedSummary } : {});
      setPublishOpen(false);
      setPublishSummary("");
      setReleaseDraft({ has_draft: false, nodes: [], version_changes: [], changes: [] });
      try {
        const nodeRows = await listQGNodes();
        setNodes(nodeRows.items);
        setNodeRuleCounts(nodePublishedRuleCounts(nodeRows.items));
        if (selectedNodeId) {
          const selectedBatchItem = batch.items.find((item) => item.qg_node_id === selectedNodeId);
          await loadNode(selectedNodeId, selectedBatchItem?.new_version_id);
        }
        await refreshRuleReleaseDraft(true);
        setMessage("规则版本发布批次已发布，新建任务将使用涉及节点的新版本规则。");
      } catch (refreshError) {
        setMessage(refreshError instanceof Error ? `规则版本发布批次已发布，但刷新失败：${refreshError.message}` : "规则版本发布批次已发布，但刷新失败");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布失败");
    } finally {
      setIsPublishing(false);
    }
  }

  return (
    <main className="page rules-workspace">
      {message ? <p className="notice">{message}</p> : null}

      <section className="rules-board">
        <aside className="rules-node-nav" aria-label="检查阶段">
          <h2>检查阶段</h2>
          {nodes.map((node) => (
            <button
              key={node.id}
              type="button"
              className={node.id === selectedNodeId ? "active" : ""}
              onClick={() => void handleSelectNode(node.id)}
            >
              <span>{node.node_code}</span>
              <strong>{nodeRuleCounts[node.id] ?? 0}</strong>
            </button>
          ))}
        </aside>

        <section className="rules-content">
          <div className="rules-content-head">
            <div>
              <div className="rules-title-row">
                <h2>{selectedNode?.node_code || "QG"} - 检查规则</h2>
                {selectedVersion ? <span>{selectedVersion.version_no}</span> : null}
              </div>
              <p>{selectedVersionMeta}</p>
              {canManageRules && selectedNodeHasPublishableDraft && selectedVersion?.id !== draftVersion?.id ? (
                <p className="rules-draft-note">
                  有待发布规则变更 {draftVersion?.version_no}
                </p>
              ) : null}
            </div>
            <button type="button" disabled={!canManageRules} onClick={() => void openCreateRuleModal()}>
              + 新增人工检查项
            </button>
          </div>

          <div className="rules-tabs" role="tablist" aria-label="检查项类型">
            <button type="button" className={activeTab === "auto" ? "active" : ""} onClick={() => setActiveTab("auto")}>
              自动检查项 <span>{autoRules.length}</span>
            </button>
            <button type="button" className={activeTab === "manual" ? "active" : ""} onClick={() => setActiveTab("manual")}>
              人工检查项 <span>{manualRules.length}</span>
            </button>
          </div>

          <div className="rules-table-wrap">
            <table className="rules-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>检查项名称</th>
                  <th>检查类型</th>
                  <th>Checklist 要求</th>
                  <th>责任方</th>
                  <th>APQP</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {visibleRules.map((rule, index) => (
                  <tr key={rule.id} className={!asBoolean(rule.is_active) ? "rules-row-disabled" : ""}>
                    <td>{index + 1}</td>
                    <td className="rules-item-name">{rule.item_name}</td>
                    <td><span className="rules-type-tag">{checkTypeLabels[rule.check_type] || itemTypeLabels[rule.item_type] || rule.check_type}</span></td>
                    <td>{rule.checklist_requirement || "-"}</td>
                    <td>{rule.owner_dept || "-"}</td>
                    <td>{asBoolean(rule.is_apqp) ? <span className="rules-check">✓</span> : "-"}</td>
                    <td><span className={asBoolean(rule.is_active) ? "rules-status active" : "rules-status disabled"}>{asBoolean(rule.is_active) ? "启用" : "停用"}</span></td>
                    <td className="rules-actions">
                      <button
                        type="button"
                        className="rules-action-btn"
                        onClick={() => void openRuleModal(rule)}
                        aria-label={canManageRules ? "编辑检查项" : "查看检查项"}
                        title={canManageRules ? "编辑检查项" : "查看检查项"}
                      >
                        {canManageRules ? "✎" : "↗"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!visibleRules.length ? (
                  <tr>
                    <td colSpan={8} className="rules-empty">暂无检查项。</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </section>

      {historyOpen ? (
        <div className="rules-drawer-backdrop" onClick={() => setHistoryOpen(false)}>
          <aside className="rules-history-drawer" onClick={(event) => event.stopPropagation()}>
            <header>
              <h2>版本历史 - {selectedNode?.node_code || "QG"}</h2>
              <button type="button" onClick={() => setHistoryOpen(false)}>×</button>
            </header>
            <div className="rules-history-list">
              {historyVersions.map((version) => (
                <article key={version.id}>
                  <div className="rules-history-main">
                    <strong>{version.version_no}</strong>
                    <span>{formatDate(version.published_at)}</span>
                    <span>{version.published_by_name || "-"}</span>
                    {version.is_current ? <em>当前版本</em> : <em>{versionStatusLabel(version.status)}</em>}
                  </div>
                  <p>{version.change_summary || "未填写变更说明"}</p>
                  <button type="button" className="link-button" onClick={() => setExpandedHistoryId(expandedHistoryId === version.id ? null : version.id)}>
                    查看变更详情
                  </button>
                  {expandedHistoryId === version.id ? (
                    <ul className="plain-list">
                      {(version.change_details || []).map((item, index) => (
                        <li key={`${version.id}-${item.item_name}-${index}`}>
                          <div>{formatRuleChangeLine(item)}</div>
                          {item.change_details?.length ? (
                            <ul className="plain-list">
                              {item.change_details.map((detail) => (
                                <li key={`${version.id}-${item.rule_code}-${detail.field}`}>
                                  {formatRuleFieldChangeLine(detail)}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))}
              {!historyVersions.length ? <p>暂无版本历史。</p> : null}
            </div>
          </aside>
        </div>
      ) : null}

      {ruleModalOpen ? (
        <div className="rules-modal-backdrop" role="dialog" aria-modal="true" aria-label={ruleModalReadonly ? "检查项详情" : editingRuleId ? "编辑检查项" : "新增人工检查项"}>
          <form className="rules-modal" onSubmit={handleSaveRule}>
            <header>
              <h2>{ruleModalReadonly ? "检查项详情" : editingRuleId ? "编辑检查项" : "新增人工检查项"}</h2>
              <button type="button" onClick={() => closeRuleModal()}>×</button>
            </header>
            <label>
              检查项名称
              <input value={ruleForm.item_name} onChange={(event) => updateRuleFormField("item_name", event.target.value)} disabled={ruleModalReadonly} required />
            </label>
            <label>
              Checklist 要求
              <textarea value={ruleForm.checklist_requirement} onChange={(event) => updateRuleFormField("checklist_requirement", event.target.value)} disabled={ruleModalReadonly} />
            </label>
            <label>
              责任方
              <input value={ruleForm.owner_dept} onChange={(event) => updateRuleFormField("owner_dept", event.target.value)} disabled={ruleModalReadonly} />
            </label>
            <div className="rules-modal-grid">
              <label>
                APQP
                <select value={ruleForm.is_apqp} onChange={(event) => updateRuleFormField("is_apqp", event.target.value)} disabled={ruleModalReadonly}>
                  <option value="true">是</option>
                  <option value="false">否</option>
                </select>
              </label>
              <label>
                状态
                <select value={ruleForm.is_active} onChange={(event) => updateRuleFormField("is_active", event.target.value)} disabled={ruleModalReadonly}>
                  <option value="true">启用</option>
                  <option value="false">停用</option>
                </select>
              </label>
            </div>
            <footer>
              {!ruleModalReadonly ? (
                <>
                  <button type="submit" disabled={!selectedVersion}>
                    {editingRuleId ? "保存修改" : "确认"}
                  </button>
                  {canSubmitUpgradeSuggestion ? (
                    <button type="button" className="secondary-button" onClick={openUpgradeSuggestion}>
                      提交升级建议
                    </button>
                  ) : null}
                  {canSubmitUpgradeSuggestion && editingRuleSource ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => void stopManualRule(editingRuleSource)}
                      disabled={!asBoolean(editingRuleSource.is_active)}
                    >
                      删除检查项
                    </button>
                  ) : null}
                </>
              ) : null}
              <button type="button" className="secondary-button" onClick={() => closeRuleModal()}>关闭</button>
            </footer>
          </form>
        </div>
      ) : null}

      {publishOpen ? (
        <div className="rules-modal-backdrop" role="dialog" aria-modal="true" aria-label="发布规则版本">
          <section className="rules-modal">
            <header>
              <h2>发布规则版本</h2>
              <button type="button" onClick={() => setPublishOpen(false)}>×</button>
            </header>
            <p>发布后新建任务将使用涉及节点的新版本规则，进行中任务不受影响。</p>
            <section className="rules-publish-summary">
              <h3>涉及节点版本变更</h3>
              <ul className="plain-list">
                {(releaseDraft?.version_changes || []).map((item) => (
                  <li key={`${item.qg_node_id}-${item.new_version_id}`}>
                    {item.node_code}：{item.old_version_no || "-"}{" -> "}{item.new_version_no}
                  </li>
                ))}
              </ul>
            </section>
            <section className="rules-publish-summary">
              <h3>本次草稿变更内容</h3>
              {(releaseDraft?.nodes || []).map((node) => (
                <div key={`${node.qg_node_id}-${node.new_version_id}`} className="rules-publish-node">
                  <strong>{node.node_code}</strong>
                  <ul className="plain-list">
                    {node.changes.map((item, index) => (
                      <li key={`${node.qg_node_id}-${item.rule_code}-${item.change_type}-${index}`}>
                        <div>{formatRuleChangeLine(item)}</div>
                        {item.change_details?.length ? (
                          <ul className="plain-list">
                            {item.change_details.map((detail) => (
                              <li key={`${node.qg_node_id}-${item.rule_code}-${detail.field}`}>
                                {formatRuleFieldChangeLine(detail)}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
            <label>
              本次总体规则版本变更说明
              <textarea value={publishSummary} onChange={(event) => setPublishSummary(event.target.value)} placeholder="选填，填写后将记入版本历史" />
            </label>
            <footer>
              <button type="button" disabled={isPublishing} onClick={() => void confirmPublish()}>
                {isPublishing ? "发布中..." : "确认发布规则版本"}
              </button>
              <button type="button" className="secondary-button" onClick={() => setPublishOpen(false)}>取消</button>
            </footer>
          </section>
        </div>
      ) : null}
    </main>
  );
}
