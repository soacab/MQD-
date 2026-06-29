# CheckFlow MVP 开发任务拆分 v1.0

## 1. 文档目的

本文档用于把 CheckFlow 从设计阶段推进到开发阶段，明确第一版 MVP 应该先开发哪些能力、暂缓哪些能力、各阶段的开发顺序、接口优先级和验收标准。

本文档承接：

```
01. CheckFlow 领域模型设计 v1.0
02. CheckFlow 系统架构设计 v1.0
03. CheckFlow 数据库设计 v1.1
04. CheckFlow 状态机设计 v1.0
05. CheckFlow API 设计 v1.0
```

MVP 目标不是一次性做完整系统，而是先做出一个能真实跑通点检主流程的版本：

```
项目创建
  ↓
规则配置
  ↓
创建点检任务
  ↓
生成检查项
  ↓
人工确认 / 简单自动检查
  ↓
归档当前轮
  ↓
生成报告
  ↓
生成整改项 / 待跟进项
  ↓
触发复查
```

---

# 2. MVP 开发总原则

## 2.1 先跑通主流程，再增强自动检查

第一版优先保证业务闭环：

```
项目 → 任务 → 轮次 → 检查项 → 工程师确认 → 归档 → 报告 → 整改 / 跟进 / 复查
```

自动检查先做最小能力：

```
VDrive 链接校验
VDrive 文件夹扫描
文件存在性判断
候选文件生成
自动检查初判写入
检查项状态联动
```

暂不优先做：

```
复杂文件内容解析
Excel深度规则判断
Word/PPT/PDF解析
QMS/UCM系统直连
LLM判断
复杂报告导出
```

---

## 2.2 状态必须由业务事件推进

开发时不要做通用状态更新接口。

禁止：

```
PATCH /inspection-tasks/{id}
{
  "status": "completed"
}
```

必须通过：

```
POST /inspection-tasks/{id}/archive-current-round
```

原因：

```
状态变更必须伴随前置校验、联动数据生成和审计日志。
```

---

## 2.3 先后端主干，再前端完整交互

建议开发顺序：

```
1. 后端数据模型
2. 后端核心 API
3. 后端状态机逻辑
4. 前端页面接入
5. VDrive 自动检查
6. 报告与复查闭环
```

不要先把前端页面做得很完整，否则后端状态机一改，前端会反复调整。

---

# 3. 技术栈建议

## 3.1 后端

```
Python
FastAPI
SQLAlchemy 2.x
Alembic
PostgreSQL
Pydantic
Redis，可二期
Celery / RQ，可二期
```

MVP 阶段如果团队较小，可以先不用 Celery，自动检查先同步执行或使用 FastAPI BackgroundTasks。等 VDrive 扫描和解析任务复杂后，再迁移到任务队列。

---

## 3.2 前端

```
React / Next.js
TypeScript
Tailwind CSS
Shadcn UI
TanStack Query
Zustand，可选
```

---

## 3.3 数据库

```
PostgreSQL
```

原因：

```
1. jsonb 支持规则快照、报告过程记录、自动检查配置。
2. 支持部分唯一索引，适合限制同一项目同一QG节点只能有一个活跃任务。
3. 适合后续做复杂查询和审计追溯。
```

---

# 4. MVP 范围定义

## 4.1 MVP 必须做

```
用户登录 / 当前用户信息
用户权限基础控制

项目创建
项目列表
项目详情
项目加单
项目软删除
VDrive 链接校验

QG节点配置
业务规则版本配置
业务检查项配置
自动检查执行规则配置，仅存配置，先不做复杂编辑器

创建点检任务
生成规则快照
生成首轮轮次
生成检查项实例

检查项列表
人工确认检查项
自动检查项转人工
归档当前轮

生成报告
报告详情
报告更正

生成整改项
标记整改完成
触发复查

生成待跟进项
关闭待跟进项

基础审计日志
```

---

## 4.2 MVP 建议做

```
VDrive 文件夹扫描
vdrive_scan_batches
vdrive_folders
vdrive_files

文件存在性自动检查
auto_check_results
auto_check_candidate_files
candidate_waiting 状态
选择候选文件
```

---

## 4.3 MVP 暂缓做

```
文件内容解析判断
Excel / Word / PPT / PDF 深度解析
OCR
LLM 判断
QMS 接口
UCM 接口
复杂导出 PDF / Word
复杂仪表盘
多角色精细字段权限
消息通知
任务队列可视化
```

暂缓原因：

```
这些能力依赖主流程稳定。
主流程未跑通前，过早做复杂自动检查，会导致开发成本和返工风险过高。
```

---

# 5. 开发阶段划分

## Phase 0：项目初始化

### 目标

搭建前后端基础工程，确保能本地启动、连接数据库、跑迁移。

### 后端任务

```
1. 创建 FastAPI 项目。
2. 配置数据库连接。
3. 配置 SQLAlchemy Base。
4. 配置 Alembic。
5. 配置环境变量。
6. 配置统一响应结构。
7. 配置异常处理。
8. 配置基础日志。
9. 配置 CORS。
10. 创建健康检查接口。
```

建议目录：

```
backend/
  app/
    main.py
    core/
      config.py
      database.py
      security.py
      exceptions.py
    models/
    schemas/
    services/
    repositories/
    api/
      v1/
    integrations/
      vdrive/
    utils/
  alembic/
  tests/
```

### 前端任务

```
1. 创建 Next.js / React 项目。
2. 配置路由。
3. 配置 API Client。
4. 配置登录态存储。
5. 配置基础布局。
6. 配置组件库。
```

### 验收标准

```
1. 后端 /health 可以访问。
2. 数据库连接成功。
3. Alembic 可以生成和执行迁移。
4. 前端可以启动。
5. 前端可以调用后端健康检查接口。
```

---

# 6. Phase 1：数据库与基础模型

## 6.1 目标

先把核心表建出来，后续 API 基于真实数据库开发。

## 6.2 建表顺序

第一批：用户与基础配置

```
users
user_permissions
system_settings
audit_logs
```

第二批：项目域

```
projects
project_orders
project_models
```

第三批：规则域

```
qg_nodes
business_rule_versions
business_check_rules
auto_check_execution_rules
rule_snapshots
```

第四批：点检域

```
inspection_tasks
inspection_rounds
inspection_items
engineer_decisions
rectification_items
followup_items
```

第五批：自动检查域

```
auto_check_results
auto_check_candidate_files
vdrive_scan_batches
vdrive_folders
vdrive_files
```

第六批：报告域

```
inspection_reports
report_items
report_corrections
```

file_parse_jobs 可暂缓：

```
如果 MVP 不做文件内容解析，file_parse_jobs 可以先不建。
如果要提前铺路，也可以建表但不接业务。
```

## 6.3 ORM Model 编写顺序

```
User
UserPermission

Project
ProjectOrder
ProjectModel

QGNode
BusinessRuleVersion
BusinessCheckRule
AutoCheckExecutionRule
RuleSnapshot

InspectionTask
InspectionRound
InspectionItem
EngineerDecision

AutoCheckResult
AutoCheckCandidateFile

RectificationItem
FollowUpItem

InspectionReport
ReportItem
ReportCorrection

AuditLog
```

## 6.4 必须实现的数据库约束

```
users.uid 唯一
qg_nodes.node_code 唯一
business_rule_versions(qg_node_id, version_no) 唯一
business_check_rules(business_rule_version_id, rule_code) 唯一
rule_snapshots.inspection_task_id 唯一
inspection_rounds(inspection_task_id, round_no) 唯一
inspection_reports.inspection_task_id 唯一
report_items(report_id, source_rule_code) 唯一
user_permissions(user_id, permission_code) 唯一
```

活跃任务唯一约束：

```sql
CREATE UNIQUE INDEX uq_active_task_per_project_node
ON inspection_tasks(project_id, qg_node_id)
WHERE status IN ('running', 'rectifying');
```

## 6.5 验收标准

```
1. 所有 MVP 必需表可成功迁移。
2. ORM Model 可正常创建、查询、更新。
3. 基础枚举值统一定义。
4. 核心唯一约束生效。
5. 可插入一组测试数据。
```

---

# 7. Phase 2：用户、权限与项目管理

## 7.1 目标

先完成项目基础数据维护，因为点检任务必须依赖项目。

## 7.2 后端 API

```
POST /api/v1/auth/login
GET  /api/v1/auth/me

GET  /api/v1/users
POST /api/v1/users
PUT  /api/v1/users/{user_id}/permissions
POST /api/v1/users/{user_id}/enable
POST /api/v1/users/{user_id}/disable

GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/orders
DELETE /api/v1/projects/{project_id}
```

## 7.3 VDrive 链接校验 API

```
POST /api/v1/vdrive/validate-folder-link
POST /api/v1/projects/{project_id}/vdrive-link
```

MVP 可以先 mock VDrive 接口：

```
输入 VDrive URL
解析 folderGuid
返回模拟 folderId / folderName
```

等业务主流程跑通后，再接真实 VDrive。

## 7.4 前端页面

```
登录页
工作台布局
项目列表页
项目详情页
新建项目弹窗 / 页面
项目加单
项目删除确认
VDrive 链接校验结果展示
```

## 7.5 验收标准

```
1. 可以创建项目。
2. 可以保存 VDrive URL、folderGuid、folderId。
3. 可以查看项目列表和详情。
4. 可以加单并新增机型。
5. 删除项目后，普通列表不展示。
6. deleted 项目不能再创建点检任务。
```

---

# 8. Phase 3：规则配置

## 8.1 目标

完成点检任务创建前的规则配置能力。

## 8.2 后端 API

```
GET  /api/v1/qg-nodes

GET  /api/v1/business-rule-versions
POST /api/v1/business-rule-versions
GET  /api/v1/business-rule-versions/{version_id}

POST  /api/v1/business-rule-versions/{version_id}/business-check-rules
PATCH /api/v1/business-check-rules/{rule_id}

POST  /api/v1/business-check-rules/{rule_id}/auto-check-execution-rules
PATCH /api/v1/auto-check-execution-rules/{execution_rule_id}
POST  /api/v1/auto-check-execution-rules/{execution_rule_id}/enable
POST  /api/v1/auto-check-execution-rules/{execution_rule_id}/disable

POST /api/v1/business-rule-versions/{version_id}/publish
POST /api/v1/business-rule-versions/{version_id}/deprecate
```

## 8.3 MVP 规则配置能力

业务检查项配置字段：

```
rule_code
item_name
item_type
check_type
checklist_requirement
owner_dept
is_apqp
is_active
sort_order
```

自动检查执行规则字段：

```
execution_code
execution_mode
adapter_type
config_json
config_version
is_enabled
```

## 8.4 发布校验

发布业务规则版本时必须校验：

```
1. 版本状态必须是 draft。
2. 至少有一个启用的 business_check_rule。
3. item_type = auto 的检查项必须有启用的 auto_check_execution_rule。
4. item_type = system 的检查项必须有启用的 auto_check_execution_rule。
5. item_type = manual 的检查项不需要 auto_check_execution_rule。
6. item_type = inherit 的检查项不需要 auto_check_execution_rule。
```

## 8.5 前端页面

```
QG节点规则版本列表
规则版本详情
新增检查项
编辑检查项
配置自动检查执行规则
发布规则版本
```

MVP 阶段自动检查执行规则的 `config_json` 可以先用 JSON 编辑框，不必做复杂表单。

## 8.6 验收标准

```
1. 可以创建规则版本。
2. 可以新增业务检查项。
3. 可以给自动检查项配置 auto_check_execution_rule。
4. 可以发布业务规则版本。
5. 发布后旧版本自动 deprecated。
6. 已发布版本可用于创建点检任务。
```

---

# 9. Phase 4：点检任务主流程

## 9.1 目标

完成从创建任务到归档当前轮的核心业务闭环。

## 9.2 后端 API

```
POST /api/v1/inspection-tasks
GET  /api/v1/inspection-tasks
GET  /api/v1/inspection-tasks/{task_id}
GET  /api/v1/inspection-tasks/{task_id}/current-round/items

POST /api/v1/inspection-items/{item_id}/confirm
POST /api/v1/inspection-items/{item_id}/convert-to-manual

POST /api/v1/inspection-tasks/{task_id}/archive-current-round
POST /api/v1/inspection-tasks/{task_id}/void
```

## 9.3 创建点检任务逻辑

CreateInspectionTask 必须完成：

```
1. 校验项目 status = normal。
2. 校验项目存在 vdrive_folder_guid 和 vdrive_folder_id。
3. 查询当前 QG 节点 published 规则版本。
4. 校验不存在同项目同节点 running / rectifying 任务。
5. 创建 inspection_tasks，status = running。
6. 创建 rule_snapshots。
7. 冻结 business_rule_snapshot_json。
8. 冻结 auto_check_execution_rule_snapshot_json。
9. 创建 inspection_rounds，round_no = 1，status = running。
10. 根据业务检查规则快照生成 inspection_items。
11. 创建 inspection_reports。
12. 写入 audit_logs。
```

## 9.4 检查项初始状态

```
file_existence → pending
file_content → pending
system_direct → pending
manual → manual_required
inherit → inherited
```

MVP 如果暂不启用自动检查，可以先把自动检查项也允许转人工：

```
pending → manual_required → confirmed
```

## 9.5 工程师确认逻辑

ConfirmInspectionItem 需要处理：

```
1. 创建 engineer_decisions。
2. 写入 decision_result。
3. 写入 decision_text。
4. fail 时校验 responsible_owner、planned_finish_date 必填。
5. conditional 时校验 countermeasure、responsible_owner、planned_finish_date 必填。
6. 更新 inspection_items.final_result。
7. inspection_items.status = confirmed。
8. 写入 audit_logs。
```

## 9.6 归档当前轮逻辑

ArchiveCurrentRound 前置条件：

```
1. InspectionTask.status = running。
2. 当前 InspectionRound.status = running。
3. 所有检查项 status = confirmed 或 inherited。
```

节点结论计算：

```
存在 fail → NO_GO
不存在 fail，但存在 conditional → C_GO
其他 → FULL_GO
```

归档动作：

```
1. inspection_rounds.status = archived。
2. 写入 archived_at。
3. 更新 inspection_reports。
4. 创建或更新 report_items。
5. 写入 process_records_json。
6. 如果 NO_GO，生成 rectification_items，task.status = rectifying。
7. 如果 C_GO，生成 followup_items，task.status = completed。
8. 如果 FULL_GO，task.status = completed。
9. 写入 audit_logs。
```

## 9.7 前端页面

```
创建点检任务页
点检任务列表
点检任务详情
当前轮检查项列表
检查项确认弹窗
归档当前轮按钮
任务作废
```

## 9.8 验收标准

```
1. 可以基于已发布规则创建点检任务。
2. 可以生成首轮检查项。
3. 人工检查项可以确认。
4. 自动检查项即使未接自动检查，也可以转人工确认。
5. 所有检查项确认后可以归档。
6. FULL_GO 后任务 completed。
7. C_GO 后任务 completed 且生成待跟进项。
8. NO_GO 后任务 rectifying 且生成整改项。
9. 报告数据同步生成。
```

---

# 10. Phase 5：报告、整改、待跟进、复查

## 10.1 目标

完成点检闭环，而不是只停在首轮归档。

## 10.2 后端 API

报告：

```
GET  /api/v1/reports
GET  /api/v1/reports/{report_id}
POST /api/v1/reports/{report_id}/items/{report_item_id}/correct
```

整改：

```
GET  /api/v1/rectification-items
POST /api/v1/rectification-items/{item_id}/mark-done
POST /api/v1/rectification-items/{item_id}/reopen
```

复查：

```
POST /api/v1/inspection-tasks/{task_id}/trigger-recheck
```

待跟进：

```
GET  /api/v1/followup-items
POST /api/v1/followup-items/{item_id}/close
```

## 10.3 报告详情逻辑

报告展示：

```
项目基础信息
QG节点
综合结论
latest_round_no
检查项明细
每个检查项当前 final_result
每个检查项 process_records_json
是否已更正 corrected
更正记录
```

## 10.4 整改完成逻辑

MarkRectificationDone：

```
1. 校验任务 status = rectifying。
2. 写入 marked_done_by。
3. 写入 marked_done_at。
4. 写入 audit_logs。
```

ReopenRectificationItem：

```
1. 校验尚未触发复查。
2. 清空 marked_done_by。
3. 清空 marked_done_at。
4. 写入 audit_logs。
```

## 10.5 触发复查逻辑

TriggerRecheck 前置条件：

```
1. task.status = rectifying。
2. 最新 round.status = archived。
3. 所有 rectification_items.marked_done_at 不为空。
```

系统动作：

```
1. 创建新 inspection_rounds。
2. round_no = current_round_no + 1。
3. task.status = running。
4. task.current_round_no = 新 round_no。
5. 根据上一轮 fail 检查项生成复查 inspection_items。
6. 写入 audit_logs。
```

## 10.6 前端页面

```
报告详情页
报告更正弹窗
整改项列表
整改完成 / 撤销完成
触发复查按钮
待跟进项列表
关闭待跟进项
```

## 10.7 验收标准

```
1. NO_GO 归档后能看到整改项。
2. 所有整改项完成后可以触发复查。
3. 复查轮只生成 fail 项。
4. 复查轮可以再次确认、归档。
5. 报告中同一检查项可以看到多轮过程记录。
6. C_GO 归档后能看到待跟进项。
7. 待跟进项关闭不改变任务 completed 状态。
8. 报告更正不改变原始点检流程。
```

---

# 11. Phase 6：VDrive 文件存在性自动检查

## 11.1 目标

在主流程稳定后，接入第一类自动检查：文件存在性判断。

## 11.2 后端 API

```
POST /api/v1/projects/{project_id}/vdrive/scan
GET  /api/v1/vdrive/scan-batches/{scan_batch_id}

POST /api/v1/inspection-items/{item_id}/auto-check
POST /api/v1/inspection-items/{item_id}/auto-check/retry
GET  /api/v1/inspection-items/{item_id}/auto-check-results
GET  /api/v1/inspection-items/{item_id}/candidate-files
POST /api/v1/inspection-items/{item_id}/candidate-files/select
```

## 11.3 VDrive 扫描逻辑

```
1. 根据 project.vdrive_folder_id 作为根目录。
2. 调用 VDrive 接口获取当前文件夹文件和子文件夹。
3. 递归扫描子文件夹。
4. 创建 vdrive_scan_batches。
5. 写入 vdrive_folders。
6. 写入 vdrive_files。
7. scan_status = success / failed。
```

MVP 可先做非递归，确认接口能跑通后再做递归。

## 11.4 文件存在性判断逻辑

输入：

```
InspectionItem
AutoCheckExecutionRuleSnapshot
VDriveScanBatch
```

候选依据：

```
file_name
file_path
file_version
created_time
modified_time
file_size
```

输出：

```
auto_check_results
auto_check_candidate_files
inspection_items.status
```

## 11.5 结果处理

找到明确目标文件：

```
auto_status = success
auto_result = pass / suspect
inspection_item.status = auto_completed
```

未找到文件：

```
auto_status = manual_required
auto_result = not_found
inspection_item.status = manual_required
```

多个候选文件：

```
auto_status = candidate_waiting
auto_result = manual_required
inspection_item.status = candidate_waiting
```

VDrive 异常：

```
auto_status = manual_required
auto_result = error
inspection_item.status = manual_required
```

## 11.6 前端页面

```
自动检查状态展示
自动检查结果展示
候选文件列表
选择候选文件
重新自动检查
转人工判断
```

## 11.7 验收标准

```
1. 可以扫描 VDrive 文件夹。
2. 可以保存文件夹和文件快照。
3. 可以对 file_existence 检查项执行自动检查。
4. 未找到文件时进入 manual_required。
5. 多候选文件时进入 candidate_waiting。
6. 选择候选文件后可以继续确认检查项。
7. 自动检查结果不直接作为最终结论，仍需工程师确认。
```

---

# 12. Phase 7：基础工作台与查询

## 12.1 目标

让用户能从工作台看到自己需要处理的任务。

## 12.2 后端 API

```
GET /api/v1/dashboard/overview
GET /api/v1/dashboard/my-todos
```

## 12.3 工作台卡片

```
进行中任务
整改中任务
待确认检查项
待选择候选文件
待归档任务
超期整改项
超期待跟进项
```

## 12.4 验收标准

```
1. 用户进入系统后能看到当前待办。
2. 能从待办跳转到对应任务、检查项、整改项或报告。
3. 超期整改和超期待跟进能正确推导。
```

---

# 13. 推荐开发顺序总表

| 顺序 | 模块 | 是否阻塞主流程 | 优先级 |
| --- | --- | --- | --- |
| 1 | 后端项目初始化 | 是 | P0 |
| 2 | 数据库迁移与 ORM | 是 | P0 |
| 3 | 用户与权限 | 是 | P0 |
| 4 | 项目管理 | 是 | P0 |
| 5 | VDrive链接校验 | 是 | P0 |
| 6 | 规则版本与检查项配置 | 是 | P0 |
| 7 | 创建点检任务 | 是 | P0 |
| 8 | 生成规则快照 | 是 | P0 |
| 9 | 生成轮次和检查项 | 是 | P0 |
| 10 | 工程师确认检查项 | 是 | P0 |
| 11 | 归档当前轮 | 是 | P0 |
| 12 | 报告生成 | 是 | P0 |
| 13 | 整改项 / 待跟进项 | 是 | P0 |
| 14 | 触发复查 | 是 | P0 |
| 15 | 报告更正 | 否 | P1 |
| 16 | VDrive扫描 | 否 | P1 |
| 17 | 文件存在性自动检查 | 否 | P1 |
| 18 | 工作台统计 | 否 | P1 |
| 19 | 文件内容解析 | 否 | P2 |
| 20 | 系统直连 | 否 | P2 |
| 21 | 复杂导出 | 否 | P2 |

---

# 14. 第一轮冲刺建议

## Sprint 1：后端骨架 + 数据库

目标：

```
系统能启动，数据库能迁移，核心表可操作。
```

任务：

```
1. FastAPI 初始化。
2. PostgreSQL 连接。
3. Alembic 配置。
4. 创建基础 ORM。
5. 建立用户、项目、规则、任务核心表。
6. 写种子数据脚本。
```

验收：

```
可以通过脚本创建一个用户、一个项目、一个QG节点、一个规则版本。
```

---

## Sprint 2：项目与规则配置

目标：

```
可以配置项目和检查规则。
```

任务：

```
1. 项目 CRUD。
2. VDrive URL 解析。
3. 项目加单。
4. QG 节点列表。
5. 业务规则版本。
6. 检查项配置。
7. 自动检查执行规则配置。
8. 规则发布。
```

验收：

```
存在一个 normal 项目。
存在一个 QG 节点 published 规则版本。
规则版本下有多个检查项。
```

---

## Sprint 3：点检任务主流程

目标：

```
可以创建任务、生成检查项、人工确认、归档。
```

任务：

```
1. CreateInspectionTask。
2. 生成 RuleSnapshot。
3. 生成 Round。
4. 生成 InspectionItems。
5. 检查项列表。
6. ConfirmInspectionItem。
7. ArchiveCurrentRound。
8. 生成 ReportItems。
9. 生成 RectificationItems / FollowUpItems。
```

验收：

```
一个项目可以完成一轮点检。
FULL_GO、C_GO、NO_GO 三种结论都能跑通。
```

---

## Sprint 4：整改复查与报告

目标：

```
NO_GO 后能整改、复查，报告能展示多轮记录。
```

任务：

```
1. 整改项列表。
2. 标记整改完成。
3. 撤销整改完成。
4. TriggerRecheck。
5. 复查轮检查项生成。
6. 报告详情。
7. 报告更正。
8. 待跟进项关闭。
```

验收：

```
首轮 NO_GO 后可以整改。
整改完成后可以触发第二轮复查。
第二轮归档后报告中能看到两轮过程记录。
```

---

## Sprint 5：VDrive 文件存在性自动检查

目标：

```
自动检查能辅助识别候选文件，但最终仍由工程师确认。
```

任务：

```
1. VDrive Adapter。
2. 文件夹扫描。
3. 文件快照保存。
4. StartAutoCheck。
5. 文件存在性判断。
6. AutoCheckResult。
7. CandidateFiles。
8. SelectCandidateFile。
9. RetryAutoCheck。
```

验收：

```
file_existence 检查项可以自动扫描文件。
未找到、多候选、明确找到三种结果都能正确进入对应状态。
```

---

# 15. 暂不开发清单

第一版不要做：

```
1. 文件内容解析。
2. LLM判断。
3. OCR。
4. QMS系统直连。
5. UCM系统直连。
6. 复杂消息通知。
7. 权限到字段级。
8. 复杂报表统计。
9. 多租户。
10. 流程引擎。
11. LangGraph。
12. 完整任务队列监控。
13. 复杂导出模板。
```

说明：

```
这些不是不做，而是不作为第一版开工前置条件。
```

---

# 16. 第一版最小可演示路径

第一版演示路径应该是：

```
1. 管理员登录。
2. 创建项目。
3. 配置 VDrive 链接。
4. 创建 QG3.3 规则版本。
5. 配置 5 个检查项。
   - 2个人工项
   - 2个自动文件存在性项
   - 1个继承项
6. 发布规则版本。
7. 创建点检任务。
8. 系统生成首轮检查项。
9. 自动项先转人工或执行简单文件存在性检查。
10. 工程师确认所有检查项。
11. 归档当前轮。
12. 如果有 fail，生成整改项。
13. 标记整改完成。
14. 触发复查。
15. 复查通过。
16. 查看报告详情，能看到多轮过程记录。
```

这是 MVP 的核心验收链路。

---

# 17. 开发前最后确认清单

开始写代码前，只需要确认以下内容：

```
1. 后端技术栈是否确定。
2. 前端技术栈是否确定。
3. 数据库使用 PostgreSQL 是否确定。
4. 用户认证是自建登录还是公司统一认证。
5. VDrive 接口是否能在开发环境调用。
6. QG 节点初始枚举是否确定。
7. 第一批检查项样例是否确定。
8. 第一版是否先不做文件内容解析。
9. 第一版是否先不做 QMS / UCM。
10. 第一版报告是否先做页面展示，不做复杂导出。
```

如果以上确认，就可以开始开发。

---

# 18. 结论

CheckFlow 已经不需要继续补充大型设计文档。

当前最合理的推进方式是：

```
先开发业务主流程
再开发 VDrive 文件存在性自动检查
最后扩展文件内容解析和系统直连
```

第一阶段代码开发应从以下任务开始：

```
1. 后端项目初始化
2. 数据库迁移
3. ORM Model
4. 项目管理 API
5. 规则配置 API
6. 创建点检任务 API
7. 检查项确认 API
8. 当前轮归档 API
```

完成这些后，CheckFlow 就能进入可演示、可试用、可继续迭代的状态。