# 01 数据库迁移与 ORM

## 目标
建立 MVP 必需表、ORM 模型、枚举和核心约束，为业务 API 提供真实数据基础。

## 参考文档
- `CheckFlow 数据库设计 v1 0.md`：表结构、约束、索引。
- `CheckFlow 领域模型设计 v1 0.md`：聚合边界与对象关系。
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 1。

## 前置依赖
- [x] 00 项目初始化完成。

## 最小任务清单
- [x] T01：定义用户、权限、系统设置、审计日志 ORM；验收：模型字段覆盖 MVP 必需字段。
- [x] T02：定义项目域 ORM：`Project`、`ProjectOrder`、`ProjectModel`；验收：项目、加单、机型关系可表达。
- [x] T03：定义规则域 ORM：`QGNode`、`BusinessRuleVersion`、`BusinessCheckRule`、`AutoCheckExecutionRule`、`RuleSnapshot`；验收：业务规则和自动执行规则分表。
- [x] T04：定义点检域 ORM：`InspectionTask`、`InspectionRound`、`InspectionItem`、`EngineerDecision`、`RectificationItem`、`FollowUpItem`；验收：一任务多轮、多检查项可表达。
- [x] T05：定义自动检查与 VDrive 快照 ORM；验收：扫描批次、文件夹、文件、候选文件、自动检查结果可保存。
- [x] T06：定义报告域 ORM：`InspectionReport`、`ReportItem`、`ReportCorrection`；验收：一个任务一份报告，报告更正可追加记录。
- [x] T07：创建 Alembic 迁移；验收：全量迁移可在空库执行成功。
- [x] T08：实现唯一约束和活跃任务部分唯一索引；验收：重复数据写入被数据库阻断。
- [x] T09：添加种子数据脚本；验收：可生成管理员、QG 节点和一个草稿规则版本。

## 验收标准
- [x] 所有 MVP 表可迁移。
- [x] 核心唯一约束生效。
- [x] ORM 可完成创建、查询、更新基础操作。
- [x] 枚举值集中定义，避免散落字符串。

## 注意事项
`file_parse_jobs` 可建表但不接业务；P2 前不要实现文件内容解析流程。
