# 01 数据库迁移与轻量 SQL helper

## 目标
建立 MVP 必需表、迁移、轻量 SQL helper、集中枚举和核心约束测试，为业务 API 提供真实数据基础。

## 参考文档
- `CheckFlow 数据库设计 v1 0.md`：表结构、约束、索引。
- `CheckFlow 领域模型设计 v1 0.md`：聚合边界与对象关系。
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 1。

## 当前复核结论
当前状态为 ✅ 已按轻量 SQL helper 路线验证可用。

- 表结构、Alembic 迁移和 seed 已能支撑 P0 最小闭环。
- 当前运行时明确保留 `execute`、`query_one`、`query_all`、`transaction` 组成的轻量 SQL helper，不再把 SQLAlchemy ORM Model 作为当前 MVP Phase 1 验收项。
- 权限、用户状态、项目状态、规则版本状态、任务状态、轮次状态、检查项状态、结论和自动检查状态已集中定义在后端枚举模块中。
- 核心唯一约束已有系统性 unittest 覆盖。
- Alembic 在线迁移和 offline SQL 生成均已验证。

## 前置依赖
- [x] 00 项目初始化完成。

## 最小任务清单
- [x] T01：建立用户、权限、系统设置、审计日志表结构与 SQL helper 访问能力；验收：P0 登录、权限和审计流程可读写。
- [x] T02：建立项目域表结构与 SQL helper 访问能力：`projects`、`project_orders`、`project_models`；验收：项目、加单、机型关系可读写。
- [x] T03：建立规则域表结构与 SQL helper 访问能力：`qg_nodes`、`business_rule_versions`、`business_check_rules`、`auto_check_execution_rules`、`rule_snapshots`；验收：业务规则、自动执行规则和快照可读写。
- [x] T04：建立点检域表结构与 SQL helper 访问能力：`inspection_tasks`、`inspection_rounds`、`inspection_items`、`engineer_decisions`、`rectification_items`、`followup_items`；验收：一任务多轮、多检查项和整改复查关系可读写。
- [x] T05：建立自动检查与 VDrive 快照表结构；验收：自动检查结果、候选文件、扫描批次、文件夹、文件表可迁移，P1 前暂不接真实扫描。
- [x] T06：建立报告域表结构与 SQL helper 访问能力：`inspection_reports`、`report_items`、`report_corrections`；验收：一个任务一份报告，报告更正表可迁移，并预留 `report_id`、修改前结论、修改后结论和更正原因字段。报告更正业务 API 仍归属 14 模块。
- [x] T07：创建 Alembic 迁移；验收：全量迁移可在空库执行成功。
- [x] T08：实现唯一约束和活跃任务部分唯一索引；验收：核心唯一约束和活跃任务部分唯一索引有 unittest 覆盖。
- [x] T09：添加种子数据脚本；验收：可生成管理员、QG 节点和基础系统设置。
- [x] T10：集中定义基础枚举值；验收：任务状态、轮次状态、检查项状态、结论、权限等业务值集中定义并被主流程使用。
- [x] T11：明确 ORM / SQL helper 技术路线；验收：当前 MVP 保留轻量 SQL helper，ORM Model 不作为 Phase 1 验收项。
- [x] T12：补齐核心唯一约束测试；验收：覆盖 Phase 1 要求的唯一约束和活跃任务部分唯一索引。

## 验收标准
- [x] 所有 MVP 表可迁移。
- [x] Alembic online 迁移和 offline SQL 生成均可执行。
- [x] 核心唯一约束生效并有系统性测试覆盖。
- [x] 轻量 SQL helper 可完成创建、查询、更新和事务回滚基础操作。
- [x] 枚举值集中定义，避免业务代码继续扩散裸字符串。

## 后续处理建议

后续扩展 P1 前，优先控制 `backend/app/main.py` 继续膨胀；如需拆分服务、路由和仓储，应在轻量 SQL helper 路线下逐步抽取，不在当前阶段引入全量 SQLAlchemy ORM 迁移。

## 注意事项
`file_parse_jobs` 可建表但不接业务；P2 前不要实现文件内容解析流程。
