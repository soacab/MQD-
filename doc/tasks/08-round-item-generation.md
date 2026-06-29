# 08 生成轮次和检查项

## 目标
点检任务创建后生成首轮 InspectionRound 和基于规则快照的 InspectionItem 实例。

## 参考文档
- `CheckFlow 领域模型设计 v1 0.md`：Inspection Domain。
- `CheckFlow 状态机设计 v0 1 38e75a5befd780dd9656d2f830f35f3e.md`：InspectionRound、InspectionItem 初始状态。
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 4。

## 前置依赖
- [ ] 07 生成规则快照完成。

## 最小任务清单
- [ ] T01：在创建任务事务中创建第 1 轮 `inspection_rounds`；验收：`round_no = 1`、状态为 `running`。
- [ ] T02：从业务规则快照生成 `inspection_items`；验收：每条启用规则生成一个实例。
- [ ] T03：复制检查项展示字段到实例快照字段；验收：规则变更后实例展示不变化。
- [ ] T04：按检查类型设置初始状态；验收：manual 为 `manual_required`，inherit 为 `inherited`，自动项为 `pending`。
- [ ] T05：实现当前轮检查项列表接口；验收：按 `sort_order` 返回检查项。
- [ ] T06：实现点检执行页检查项导航；验收：左侧可切换检查项，详情区展示规则快照。
- [ ] T07：处理 QG4 继承项展示；验收：有前序记录则展示继承结论，无记录则展示缺失提示。
- [ ] T08：接入自动检查调度触发点；验收：任务创建后，符合 `file_existence` 且有启用执行规则快照的 `pending` 项进入自动检查链路。

## 验收标准
- [ ] 创建任务后自动生成首轮。
- [ ] 首轮检查项数量与快照中启用规则一致。
- [ ] 检查项初始状态符合状态机设计。
- [ ] 自动检查关闭或规则未启用时，自动项有明确转人工路径。

## 注意事项
InspectionItem 是规则生成的实例，不允许直接引用可变 BusinessCheckRule 作为展示来源。
