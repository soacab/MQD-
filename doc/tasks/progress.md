# CheckFlow MVP 任务进度

## 总体说明
本文件用于跟踪 `doc/tasks/` 下各模块任务完成情况。勾选模块前，应先完成对应模块文件内的全部最小任务和验收标准。

## P0 主流程必做
- [ ] 00 项目初始化：`00-project-bootstrap.md`
- [ ] 01 数据库迁移与 ORM：`01-database-orm.md`
- [ ] 02 用户、认证与权限：`02-auth-user-permission.md`
- [ ] 03 项目管理：`03-project-management.md`
- [ ] 04 VDrive 链接校验：`04-vdrive-link-validation.md`
- [ ] 05 规则配置与版本管理：`05-rule-config-versioning.md`
- [ ] 06 创建点检任务：`06-inspection-task-creation.md`
- [ ] 07 生成规则快照：`07-rule-snapshot.md`
- [ ] 08 生成轮次和检查项：`08-round-item-generation.md`
- [ ] 09 工程师确认检查项：`09-inspection-item-confirmation.md`
- [ ] 10 归档当前轮：`10-round-archive.md`
- [ ] 11 报告生成：`11-report-generation.md`
- [ ] 12 整改项与待跟进项：`12-rectification-followup.md`
- [ ] 13 触发复查：`13-recheck.md`

## P1 增强能力
- [ ] 14 报告更正：`14-report-correction.md`
- [ ] 15 VDrive 文件夹扫描：`15-vdrive-scan.md`
- [ ] 16 文件存在性自动检查：`16-file-existence-autocheck.md`
- [ ] 17 工作台与查询：`17-dashboard-query.md`

## P2 暂缓模块
- [ ] 18 文件内容解析（暂缓）：`18-file-content-parsing.md`
- [ ] 19 系统直连检查（暂缓）：`19-system-direct-check.md`
- [ ] 20 导出能力（暂缓）：`20-export.md`

## 阶段验收
- [ ] Sprint 1：后端骨架、数据库迁移、核心表和种子数据可用。
- [ ] Sprint 2：项目、VDrive 链接校验、规则配置和规则发布可用。
- [ ] Sprint 3：创建任务、生成检查项、人工确认、归档和报告生成可用。
- [ ] Sprint 4：整改、复查、待跟进、报告更正和多轮过程记录可用。
- [ ] Sprint 5：VDrive 扫描与文件存在性自动检查可用。

## 使用规则
- [ ] 每次实现模块前，先读取对应模块文件的目标、前置依赖和验收标准。
- [ ] 每完成一个子任务，更新对应模块文件中的 checklist。
- [ ] 每完成一个模块，更新本文件中的模块 checklist。
- [ ] P2 暂缓模块只有在 P0/P1 验收通过后再开始。
