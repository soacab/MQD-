# 09 工程师确认检查项

## 目标
实现工程师对检查项给出最终结论，并记录判定说明、责任人、对策和审计记录。

## 参考文档
- `企业办公_点检AI方案设计.md`：4.4 点检执行与结论确认。
- `CheckFlow 状态机设计 v0 1 38e75a5befd780dd9656d2f830f35f3e.md`：ConfirmInspectionItem、ConvertToManual。
- `CheckFlow 后端 API 设计 v0 1.md .md`：Inspection Item API。

## 前置依赖
- [x] 生成轮次和检查项最小链路已在 `progress.md` 中标记为可支撑当前模块。

## 最小任务清单
- [x] T01：实现 `POST /api/v1/inspection-items/{item_id}/confirm`；验收：可提交 pass、fail、conditional、na。
- [x] T02：实现 fail 必填校验；验收：不满足时必须填写责任人、计划完成时间和说明。
- [x] T03：实现 conditional 必填校验；验收：必须填写对策、责任人、计划完成时间。
- [x] T04：写入 `engineer_decisions`；验收：每次确认保留判定人、时间、结论和说明。
- [x] T05：更新 `inspection_items.final_result` 与状态；验收：确认后状态为 `confirmed`。
- [x] T06：实现自动项转人工接口；验收：异常或未接自动检查时可转为人工判断。
- [x] T07：实现检查项确认弹窗；验收：不同结论展示对应必填字段。
- [x] T08：写入确认与转人工审计日志；验收：操作可追溯。
- [x] T09：实现 na 结论校验；验收：`decision_text` 必填，归档计算时按非 fail、非 conditional 处理。

## 验收标准
- [x] 人工检查项可以确认。
- [x] 自动检查项可转人工后确认。
- [x] 必填字段校验与业务规则一致。
- [x] 最终结论只由工程师确认产生。
- [x] na 结论不生成整改项或待跟进项。

## 注意事项
自动检查结果只是初判，不得直接写成最终业务结论。
