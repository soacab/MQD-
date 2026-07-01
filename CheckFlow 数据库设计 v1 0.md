# CheckFlow 数据库设计 v1.0

## 1. 文档目的

本文档用于定义 CheckFlow 一期系统的数据库表结构、字段含义、状态字段取舍、主要约束、索引建议和一期落表范围。

本文档基于：

```
01. CheckFlow 领域模型设计 v1.0
02. CheckFlow 系统架构设计 v1.0
```

数据库设计原则：

```
1. 数据库是领域模型的持久化结果，不以页面为中心建表。
2. 业务检查规则与自动检查执行规则分表存储。
3. business_check_rules 只保存业务检查项本身，不保存文件定位、匹配字眼、候选策略等执行配置。
4. auto_check_execution_rules 保存后端真实自动检查配置。
5. 点检任务创建时，必须保存业务规则快照和自动检查执行规则快照。
6. InspectionTask 是点检主聚合，InspectionRound、InspectionItem、InspectionReport、RectificationItem、FollowUpItem 均围绕它组织。
7. 一个 InspectionTask 只有一份 InspectionReport。
8. RectificationItem、FollowUpItem 不存 status，页面状态运行时推导。
9. InspectionReport 不存 status，是否更正由 ReportCorrection 推导。
10. VDrive 使用 HTTPS 文件夹链接接入，保存 folderGuid 和 folderId。
11. 所有关键业务动作必须可审计。
```

---

# 2. 聚合与表归属

## 2.1 Project 聚合

```
projects
  ├── project_orders
  └── project_models
```

说明：

```
Project 是项目基础信息根对象。
Project 被软删除后，普通列表不展示，但历史数据保留。
```

---

## 2.2 Rule 聚合

```
qg_nodes
  └── business_rule_versions
        └── business_check_rules
              └── auto_check_execution_rules
```

说明：

```
BusinessCheckRule 是业务检查项模板。
AutoCheckExecutionRule 是后端真实自动检查配置。
二者分离，但通过 business_check_rule_id 建立关系。
```

---

## 2.3 Inspection 聚合

```
inspection_tasks
  ├── rule_snapshots
  ├── inspection_rounds
  │     └── inspection_items
  │           ├── auto_check_results
  │           │     └── auto_check_candidate_files
  │           └── engineer_decisions
  │
  ├── rectification_items
  ├── followup_items
  └── inspection_reports
        └── report_items
              └── report_corrections
```

说明：

```
InspectionTask 是点检业务主聚合根。
InspectionRound 是任务下的第 N 轮执行。
InspectionItem 是某一轮的检查项实例。
InspectionReport 属于 InspectionTask，不属于 InspectionRound。
```

---

## 2.4 User & Admin 聚合

```
users
  └── user_permissions

system_settings
audit_logs
```

---

# 3. 表关系总览

```
projects.id
  → project_orders.project_id
  → project_models.project_id
  → inspection_tasks.project_id

qg_nodes.id
  → business_rule_versions.qg_node_id
  → business_check_rules.qg_node_id
  → inspection_tasks.qg_node_id
  → inspection_reports.qg_node_id

business_rule_versions.id
  → business_check_rules.business_rule_version_id

business_check_rules.id
  → auto_check_execution_rules.business_check_rule_id

inspection_tasks.id
  → rule_snapshots.inspection_task_id
  → inspection_rounds.inspection_task_id
  → inspection_items.inspection_task_id
  → rectification_items.inspection_task_id
  → followup_items.inspection_task_id
  → inspection_reports.inspection_task_id

inspection_rounds.id
  → inspection_items.inspection_round_id
  → rectification_items.source_round_id
  → followup_items.source_round_id

inspection_items.id
  → auto_check_results.inspection_item_id
  → engineer_decisions.inspection_item_id
  → rectification_items.source_item_id
  → followup_items.source_item_id

auto_check_results.id
  → auto_check_candidate_files.auto_check_result_id

inspection_reports.id
  → report_items.report_id

report_items.id
  → report_corrections.report_item_id
```

---

# 4. 项目域表

## 4.1 projects：项目表

业务定义：

```
保存项目基础信息、VDrive 项目文件夹链接和项目展示状态。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 项目ID |
| project_name | varchar | 项目名称 |
| customer | varchar | 客户名称 |
| project_category | varchar | 项目类别，如新项目、改款、平台延伸 |
| bu | varchar | 所属 BU |
| project_level | varchar | 项目等级 |
| mq_user_id | bigint / uuid | 负责 MQ 工程师用户ID |
| mq_user_name_snapshot | varchar | MQ 工程师姓名快照 |
| mp_owner | varchar | 对应 MP / 项目经理 |
| group_name | varchar | 小组 |
| planned_mp_date | date | 计划量产时间 |
| production_line | varchar | 生产线体 |
| vdrive_url | text | 用户粘贴的 VDrive 文件夹链接 |
| vdrive_folder_guid | varchar | 从链接解析出的 folderGuid |
| vdrive_folder_id | bigint | VDrive 接口返回的文件夹数字ID |
| vdrive_folder_name | varchar | VDrive 文件夹名称 |
| vdrive_folder_path | varchar | VDrive 接口返回的文件夹路径 |
| status | varchar | 项目状态：normal / deleted |
| created_by | bigint / uuid | 创建人 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |
| deleted_by | bigint / uuid | 删除人 |
| deleted_at | timestamp | 删除时间 |
| delete_reason | text | 删除原因，可选 |

status 枚举：

```
normal     正常
deleted    已删除，软删除，不在普通列表展示
```

说明：

```
删除项目不是物理删除。
项目删除后，相关任务、报告、自动检查结果、整改、待跟进和审计日志均保留。
```

---

## 4.2 project_orders：项目接收批次表

业务定义：

```
保存项目接收时间和加单批次。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 接收批次ID |
| project_id | bigint / uuid | 所属项目ID |
| receive_date | date | 项目接收时间 |
| created_by | bigint / uuid | 创建人 |
| created_at | timestamp | 创建时间 |

说明：

```
一个项目可以有多个接收批次。
加单时新增一条 project_orders 记录。
```

---

## 4.3 project_models：项目机型表

业务定义：

```
保存某个接收批次下的机型。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 机型记录ID |
| project_id | bigint / uuid | 所属项目ID |
| project_order_id | bigint / uuid | 所属接收批次ID |
| model_name | varchar | 机型名称 |
| created_at | timestamp | 创建时间 |

说明：

```
一个接收批次可以有多个机型。
PIL、UCM 等系统直连检查通常需要按机型执行。
```

---

# 5. 规则域表

## 5.1 qg_nodes：QG 节点表

业务定义：

```
保存 QG 节点枚举和排序。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | QG节点内部ID，用于外键关联，不对业务用户展示 |
| node_code | varchar | 节点编码，如 QG2、QG3.1、QG3.2、QG3.3、QG3、QG4 |
| sort_order | int | QG节点流程排序，用于推荐下一个节点 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

---

## 5.2 business_rule_versions：业务规则版本表

业务定义：

```
保存某个 QG 节点下的一版业务检查规则集合。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 业务规则版本ID |
| qg_node_id | bigint / uuid | 所属 QG 节点ID |
| version_no | varchar | 版本号，如 V01、V02 |
| status | varchar | 版本状态：draft / published / deprecated |
| change_summary | text | 版本变更说明 |
| published_by | bigint / uuid | 发布人 |
| published_at | timestamp | 发布时间 |
| created_by | bigint / uuid | 创建人 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

status 枚举：

```
draft        草稿
published    已发布
deprecated   已废弃
```

说明：

```
已发布版本只影响后续新建任务。
已创建任务使用 rule_snapshots，不再实时读取本表。
```

---

## 5.3 business_check_rules：业务检查规则表

业务定义：

```
保存业务侧可见的检查项模板，用于点检页面展示、报告引用和生成 InspectionItem。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 业务检查规则ID |
| business_rule_version_id | bigint / uuid | 所属业务规则版本ID |
| qg_node_id | bigint / uuid | 所属 QG 节点ID |
| rule_code | varchar | 检查项唯一编码 |
| item_name | varchar | 检查项名称，如 PFMEA、流程图、PIL问题 |
| item_type | varchar | 检查项类型：auto / manual / system / inherit |
| check_type | varchar | 检查方式：file_existence / file_content / system_direct / manual / inherit |
| checklist_requirement | text | Checklist 要求 |
| owner_dept | varchar | 责任方，如 MQD、PT、TE、MP |
| is_apqp | boolean | 是否属于 APQP 内容 |
| is_active | boolean | 是否启用 |
| sort_order | int | 展示顺序 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

item_type 枚举：

```
auto      自动检查项
manual    人工检查项
system    系统直连项
inherit   继承项
```

check_type 枚举：

```
file_existence    文件存在性判断
file_content      文件内容判断
system_direct     系统直连判断
manual            人工判断
inherit           继承前序结果
```

关键说明：

```
business_check_rules 不保存文件定位、匹配字眼、候选文件策略、解析器、Prompt 或模型配置。
这些后端真实执行配置统一保存于 auto_check_execution_rules。
人工检查项只需要 business_check_rules，不需要 auto_check_execution_rules。
```

---

## 5.4 auto_check_execution_rules：自动检查执行规则表

业务定义：

```
保存后端真实自动检查执行配置，用于文件存在性判断、文件内容判断、系统直连判断和异常降级。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 自动检查执行规则ID |
| business_check_rule_id | bigint / uuid | 关联业务检查规则ID |
| execution_code | varchar | 执行规则编码 |
| execution_mode | varchar | 执行模式：file_existence / file_content / system_direct |
| adapter_type | varchar | 外部适配器类型：vdrive / qms / ucm / none |
| config_json | jsonb | 自动检查执行配置 JSON |
| config_version | varchar | 执行配置版本号 |
| is_enabled | boolean | 是否启用 |
| created_by | bigint / uuid | 创建人 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

execution_mode 枚举：

```
file_existence    文件存在性判断
file_content      文件内容判断
system_direct     系统直连判断
```

adapter_type 枚举：

```
vdrive
qms
ucm
none
```

说明：

```
不是所有自动检查都需要 LLM。
文件存在性判断主要基于 VDrive 文件元数据。
文件内容判断必须先执行文件存在性判断，找到目标文件后才下载并解析。
系统直连判断通过 QMS、UCM 等外部系统接口获取结构化数据。
```

---

### 5.4.1 file_existence 配置示例

文件存在性判断用于判断目标文件是否存在、是否满足时效要求，判断依据主要来自 VDrive 文件元数据：

```
文件名称
文件路径
文件版本
文件创建时间
文件修改时间
文件大小
```

配置示例：

```
{
  "execution_mode": "file_existence",
  "file_existence": {
    "candidate_basis": [
      "file_name",
      "file_path",
      "file_version",
      "created_time",
      "modified_time",
      "file_size"
    ],
    "candidate_strategy": "by_check_item_config",
    "time_check": {
      "enabled": true,
      "field": "modified_time",
      "within_days": 60
    },
    "candidate_ranking": [
      {
        "field": "modified_time",
        "order": "desc"
      },
      {
        "field": "file_size",
        "order": "desc"
      }
    ]
  },
  "fallback": {
    "no_candidate": "manual_required",
    "multiple_candidates": "candidate_waiting",
    "vdrive_error": "manual_required"
  }
}
```

---

### 5.4.2 file_content 配置示例

文件内容判断不是独立从零开始执行。

文件内容判断必须先执行文件存在性判断：

```
先扫描 VDrive
  ↓
基于文件元数据识别候选文件
  ↓
确认目标文件存在
  ↓
下载文件
  ↓
按检查项配置的解析规则解析文件
  ↓
执行内容判断
```

配置示例：

```
{
  "execution_mode": "file_content",
  "file_existence": {
    "candidate_basis": [
      "file_name",
      "file_path",
      "file_version",
      "created_time",
      "modified_time",
      "file_size"
    ],
    "candidate_strategy": "by_check_item_config",
    "candidate_ranking": [
      {
        "field": "modified_time",
        "order": "desc"
      },
      {
        "field": "file_size",
        "order": "desc"
      }
    ]
  },
  "file_download": {
    "required": true
  },
  "content_parse": {
    "parser_type": "excel",
    "parser_rule_code": "dfa_issue_closure_v1"
  },
  "content_validation": {
    "validation_rule_code": "all_target_issues_closed"
  },
  "fallback": {
    "no_candidate": "manual_required",
    "multiple_candidates": "candidate_waiting",
    "download_failed": "manual_required",
    "parse_failed": "manual_required",
    "unsupported_file_type": "manual_required"
  }
}
```

说明：

```
若未找到候选文件、候选文件无法确认、下载失败或解析失败，则降级为人工判断。
不同文件内容检查项可以使用不同 parser_rule_code 和 validation_rule_code。
```

---

### 5.4.3 system_direct 配置示例

系统直连判断用于 QMS、UCM 等外部系统查询类检查项。

配置示例：

```
{
  "execution_mode": "system_direct",
  "system_direct": {
    "adapter": "qms",
    "query_type": "pil_by_model",
    "model_source": "project_models",
    "validation": {
      "min_close_rate": 80,
      "blocked_unclosed_severity": ["A", "B"]
    },
    "result_aggregation": {
      "multi_model_strategy": "any_model_fail_then_fail"
    }
  },
  "fallback": {
    "external_system_error": "manual_required",
    "no_data": "manual_required"
  }
}
```

---

## 5.5 rule_snapshots：规则快照表

业务定义：

```
保存点检任务创建时冻结的业务规则快照和自动检查执行规则快照。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 规则快照ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| business_rule_version_id | bigint / uuid | 来源业务规则版本ID |
| business_rule_snapshot_json | jsonb | 业务规则快照 |
| auto_check_execution_rule_snapshot_json | jsonb | 自动检查执行规则快照 |
| created_at | timestamp | 快照创建时间 |

说明：

```
任务执行、复查、报告展示均读取快照。
规则发布或自动检查执行规则修改，不影响已创建任务。
```

# 6. 点检域表

## 6.1 inspection_tasks：点检任务表

业务定义：

```
保存一个项目在某个 QG 节点下的一次完整点检任务。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 点检任务ID |
| project_id | bigint / uuid | 所属项目ID |
| qg_node_id | bigint / uuid | QG 节点ID |
| rule_snapshot_id | bigint / uuid | 本任务绑定的规则快照ID |
| task_no | varchar | 任务编号 |
| status | varchar | 任务状态：running / rectifying / completed / voided |
| current_round_no | int | 当前轮次 |
| created_by | bigint / uuid | 创建人 |
| created_at | timestamp | 创建时间 |
| started_at | timestamp | 开始时间 |
| completed_at | timestamp | 完成时间 |
| archived_at | timestamp | 最近归档时间 |
| last_operated_at | timestamp | 最近操作时间 |
| voided_by | bigint / uuid | 作废人 |
| voided_at | timestamp | 作废时间 |
| void_reason | text | 作废原因 |

status 枚举：

```
running       点检进行中
rectifying    整改中，等待整改完成后复查
completed     已完成，FULL-GO 或 C-GO
voided        已作废，误建或业务取消
```

说明：

```
InspectionTask.status 是业务流程状态，必须入库。
```

---

## 6.2 inspection_rounds：点检轮次表

业务定义：

```
保存点检任务下的第 N 轮点检执行。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 轮次ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| round_no | int | 第几轮点检 |
| status | varchar | 轮次状态：running / archived |
| started_at | timestamp | 本轮开始时间 |
| archived_at | timestamp | 本轮归档时间 |
| created_at | timestamp | 创建时间 |

status 枚举：

```
running     本轮正在点检中
archived    本轮已归档，不可直接修改
```

说明：

```
round_no = 1 表示首轮。
round_no > 1 表示复查轮。
不需要单独 round_type。
```

---

## 6.3 inspection_items：检查项实例表

业务定义：

```
保存某一轮中的实际检查项实例。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 检查项实例ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| inspection_round_id | bigint / uuid | 所属点检轮次ID |
| source_rule_code | varchar | 来源业务检查规则编码 |
| source_business_rule_id | bigint / uuid | 来源业务检查规则ID，可选 |
| item_name_snapshot | varchar | 检查项名称快照 |
| item_type_snapshot | varchar | 检查项类型快照 |
| check_type_snapshot | varchar | 检查方式快照 |
| checklist_requirement_snapshot | text | Checklist要求快照 |
| owner_dept_snapshot | varchar | 责任方快照 |
| is_apqp_snapshot | boolean | 是否APQP快照 |
| sort_order | int | 展示顺序 |
| status | varchar | 检查项处理状态 |
| final_result | varchar | 工程师最终结论 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

status 枚举：

```
pending             待检查
checking            自动检查中
candidate_waiting   等待候选文件选择
auto_completed      自动检查完成，待工程师确认
manual_required     需人工判断
confirmed           工程师已确认
inherited           已继承
```

final_result 枚举：

```
pass           满足
fail           不满足
conditional    带条件满足
na             不适用
inherit        继承
```

说明：

```
InspectionItem 是实例，不是规则。
字段使用 snapshot 后缀，表示生成任务时从 BusinessCheckRule 快照复制。
后续业务规则修改，不影响已有 InspectionItem。
```

---

## 6.4 engineer_decisions：工程师确认表

业务定义：

```
保存工程师对某个检查项实例的最终判断。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 工程师确认记录ID |
| inspection_item_id | bigint / uuid | 所属检查项实例ID |
| decision_result | varchar | 工程师最终结论 |
| decision_text | text | 点检说明 / 判断说明 |
| responsible_owner | varchar | 责任人 |
| countermeasure | text | 对策，带条件满足时必填 |
| planned_finish_date | date | 计划完成时间 |
| override_auto_result | boolean | 是否推翻自动检查初判 |
| override_reason | text | 推翻自动检查原因 |
| decided_by | bigint / uuid | 判定人 |
| decided_at | timestamp | 判定时间 |
| created_at | timestamp | 创建时间 |

decision_result 枚举：

```
pass
fail
conditional
na
```

说明：

```
工程师最终结论参与归档和节点结论计算。
自动检查初判不直接参与最终节点结论。
```

---

## 6.5 rectification_items：整改项表

业务定义：

```
保存由不满足项生成的整改跟踪对象。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 整改项ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| source_round_id | bigint / uuid | 来源轮次ID |
| source_item_id | bigint / uuid | 来源检查项ID |
| project_id | bigint / uuid | 所属项目ID |
| item_name_snapshot | varchar | 检查项名称快照 |
| problem_desc | text | 问题描述 |
| responsible_owner | varchar | 责任人 |
| planned_finish_date | date | 计划完成时间 |
| marked_done_by | bigint / uuid | 标记完成人 |
| marked_done_at | timestamp | 标记完成时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

不存字段：

```
status
```

状态推导：

```
待整改 = marked_done_at 为空，且 planned_finish_date >= 当前日期
已超期 = marked_done_at 为空，且 planned_finish_date < 当前日期
已完成 = marked_done_at 不为空
逾期完成 = marked_done_at 不为空，且 marked_done_at > planned_finish_date
```

---

## 6.6 followup_items：待跟进项表

业务定义：

```
保存由带条件满足项生成的后续跟进对象。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 待跟进项ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| source_round_id | bigint / uuid | 来源轮次ID |
| source_item_id | bigint / uuid | 来源检查项ID |
| project_id | bigint / uuid | 所属项目ID |
| item_name_snapshot | varchar | 检查项名称快照 |
| countermeasure | text | 对策说明 |
| responsible_owner | varchar | 责任人 |
| planned_finish_date | date | 计划完成时间 |
| closed_by | bigint / uuid | 标记落实人 |
| closed_at | timestamp | 标记落实时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

不存字段：

```
status
```

状态推导：

```
待跟进 = closed_at 为空，且 planned_finish_date >= 当前日期
已超期 = closed_at 为空，且 planned_finish_date < 当前日期
已落实 = closed_at 不为空
逾期落实 = closed_at 不为空，且 closed_at > planned_finish_date
```

# 7. 自动检查域表

## 7.1 auto_check_results：自动检查初判结果表

业务定义：

```
保存自动检查产生的初判结果，包括文件存在性判断、文件内容判断和系统直连判断。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 自动检查结果ID |
| inspection_item_id | bigint / uuid | 所属检查项实例ID |
| attempt_no | int | 第几次执行，支持重试或候选文件重跑 |
| is_latest | boolean | 是否为当前最新结果 |
| auto_status | varchar | 自动检查执行状态 |
| auto_result | varchar | 自动检查初判结果 |
| confidence | numeric | 置信度，可选 |
| evidence_text | text | 判断依据文本 |
| source_system | varchar | 数据来源：vdrive / qms / ucm / parser / llm |
| scan_root_folder_id | bigint | 扫描根文件夹ID |
| scan_root_folder_guid | varchar | 扫描根文件夹GUID |
| selected_candidate_file_id | bigint / uuid | 选中的候选文件ID，可选 |
| execution_rule_snapshot | jsonb | 本次执行使用的自动检查执行规则快照片段 |
| raw_result_json | jsonb | 原始返回结果 |
| error_code | varchar | 异常编码 |
| error_message | text | 异常说明 |
| started_at | timestamp | 开始时间 |
| finished_at | timestamp | 完成时间 |
| created_at | timestamp | 创建时间 |

auto_status 枚举：

```
success              执行成功
failed               执行失败
candidate_waiting    等待候选文件选择
manual_required      无法自动判断，需人工处理
```

auto_result 枚举：

```
pass
fail
not_found
suspect
manual_required
error
```

说明：

```
AutoCheckResult 是初判，不是最终结论。
一个 InspectionItem 可能有多次 AutoCheckResult，例如候选文件选择后重新执行。
```

---

## 7.2 auto_check_candidate_files：自动检查候选文件表

业务定义：

```
保存自动检查扫描或工程师手动补充的候选文件。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 候选文件ID |
| auto_check_result_id | bigint / uuid | 所属自动检查结果ID |
| vdrive_file_id | bigint | VDrive 文件数字ID |
| file_guid | varchar | VDrive 文件GUID |
| file_name | varchar | 文件名称 |
| file_ext | varchar | 文件扩展名 |
| file_path | text | 文件路径 |
| file_size | bigint | 文件大小 |
| file_version | varchar | 文件版本 |
| created_time | timestamp | 文件创建时间 |
| modified_time | timestamp | 文件修改时间 |
| recommend_score | numeric | 推荐分数 |
| recommend_reason | text | 推荐原因 |
| is_recommended | boolean | 是否系统推荐 |
| is_selected | boolean | 是否被工程师选中 |
| source_type | varchar | 来源类型 |
| created_at | timestamp | 创建时间 |

source_type 枚举：

```
system_scanned
manual_added
```

说明：

```
候选文件判断主要依据 VDrive 文件元数据。
```

---

## 7.3 file_parse_jobs：文件解析任务表

业务定义：

```
保存文件下载、解析、OCR、LLM 调用等异步任务记录。
文件内容判断类检查项会先完成文件存在性判断，确认目标文件后，才创建下载和解析任务。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 解析任务ID |
| inspection_item_id | bigint / uuid | 对应检查项实例ID |
| auto_check_result_id | bigint / uuid | 对应自动检查结果ID，可选 |
| candidate_file_id | bigint / uuid | 对应候选文件ID，可选 |
| job_type | varchar | 任务类型 |
| status | varchar | 任务状态 |
| parser_type | varchar | 解析器类型 |
| parser_rule_code | varchar | 解析规则编码 |
| object_key | text | 下载后保存到对象存储的文件地址 |
| parsed_result_json | jsonb | 解析结果 |
| error_code | varchar | 异常编码 |
| error_message | text | 异常说明 |
| started_at | timestamp | 开始时间 |
| finished_at | timestamp | 完成时间 |
| created_at | timestamp | 创建时间 |

job_type 枚举：

```
download
parse_excel
parse_word
parse_ppt
parse_pdf
ocr
llm_check
```

status 枚举：

```
pending
running
success
failed
```

说明：

```
file_parse_jobs.status 是异步任务生命周期状态，需要入库。
```

# 8. 报告域表

## 8.1 inspection_reports：节点报告表

业务定义：

```
保存一个点检任务对应的一份节点报告。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 报告ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| project_id | bigint / uuid | 所属项目ID |
| qg_node_id | bigint / uuid | 所属 QG 节点ID |
| report_no | varchar | 报告编号 |
| overall_result | varchar | 当前综合结论 |
| latest_round_no | int | 当前报告汇总到第几轮 |
| business_rule_version_no | varchar | 业务规则版本号快照 |
| generated_by | bigint / uuid | 首次生成人 |
| generated_at | timestamp | 首次生成时间 |
| last_modified_at | timestamp | 最近修改时间 |
| summary_json | jsonb | 报告摘要统计 |

overall_result 枚举：

```
FULL_GO
C_GO
NO_GO
```

不存字段：

```
status
```

报告是否更正推导：

```
已更正 = 存在 report_corrections
正常 = 不存在 report_corrections
```

说明：

```
一个 InspectionTask 只有一份 InspectionReport。
InspectionReport 不属于 InspectionRound。
```

---

## 8.2 report_items：报告明细表

业务定义：

```
保存报告中的检查项明细和多轮过程记录。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 报告明细ID |
| report_id | bigint / uuid | 所属报告ID |
| source_rule_code | varchar | 来源规则编码 |
| item_name_snapshot | varchar | 检查项名称快照 |
| item_type_snapshot | varchar | 检查项类型快照 |
| check_type_snapshot | varchar | 检查方式快照 |
| checklist_requirement_snapshot | text | Checklist要求快照 |
| latest_inspection_item_id | bigint / uuid | 最近一次对应的检查项实例ID |
| auto_result_snapshot | jsonb | 最近一次自动检查初判快照 |
| engineer_decision_snapshot | jsonb | 最近一次工程师确认快照 |
| final_result | varchar | 当前最终结论 |
| process_records_json | jsonb | 多轮过程记录 |
| sort_order | int | 展示顺序 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

说明：

```
一个检查项在报告中通常只有一条 ReportItem。
多轮过程记录进入 process_records_json。
报告中的数据来源来自 auto_result_snapshot 和 process_records_json，不来自 business_check_rules。
```

---

## 8.3 report_corrections：报告更正表

业务定义：

```
保存报告明细的人工更正记录。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 更正记录ID |
| report_id | bigint / uuid | 所属报告ID，冗余字段，便于查询 |
| report_item_id | bigint / uuid | 被更正的报告明细ID |
| before_result | varchar | 更正前结论 |
| after_result | varchar | 更正后结论 |
| correction_reason | text | 更正说明 |
| corrected_by | bigint / uuid | 更正人 |
| corrected_at | timestamp | 更正时间 |
| created_at | timestamp | 创建时间 |

说明：

```
更正不覆盖自动检查原始结论。
更正不删除原始过程记录。
更正只追加记录。
```

# 9. VDrive 快照表

## 9.1 vdrive_scan_batches：VDrive 扫描批次表

业务定义：

```
保存某次任务或某轮次对 VDrive 文件夹的扫描记录。
```

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 扫描批次ID |
| inspection_task_id | bigint / uuid | 所属点检任务ID |
| inspection_round_id | bigint / uuid | 所属轮次ID |
| root_folder_guid | varchar | 根文件夹GUID |
| root_folder_id | bigint | 根文件夹数字ID |
| scan_status | varchar | 扫描状态 |
| started_at | timestamp | 开始扫描时间 |
| finished_at | timestamp | 完成扫描时间 |
| error_message | text | 异常说明 |
| created_at | timestamp | 创建时间 |

scan_status 枚举：

```
pending
running
success
failed
```

说明：

```
扫描是异步过程，scan_status 需要入库。
```

---

## 9.2 vdrive_folders：VDrive 文件夹快照表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 系统内部记录ID |
| scan_batch_id | bigint / uuid | 所属扫描批次ID |
| folder_guid | varchar | VDrive 文件夹GUID |
| folder_id | bigint | VDrive 文件夹数字ID |
| parent_folder_id | bigint | 父文件夹ID |
| folder_name | varchar | 文件夹名称 |
| folder_path | text | VDrive 返回的文件夹路径 |
| creator_name | varchar | 创建人 |
| created_time | timestamp | 创建时间 |
| is_deleted | boolean | VDrive中是否已删除 |
| created_at | timestamp | 记录创建时间 |

---

## 9.3 vdrive_files：VDrive 文件快照表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 系统内部记录ID |
| scan_batch_id | bigint / uuid | 所属扫描批次ID |
| file_guid | varchar | VDrive 文件GUID |
| file_id | bigint | VDrive 文件数字ID |
| parent_folder_id | bigint | 所属文件夹ID |
| file_name | varchar | 文件名称 |
| file_ext | varchar | 文件扩展名 |
| file_size | bigint | 文件大小 |
| file_version | varchar | 文件版本 |
| creator_name | varchar | 创建人 |
| created_time | timestamp | 文件创建时间 |
| modified_time | timestamp | 文件修改时间 |
| is_deleted | boolean | VDrive中是否已删除 |
| created_at | timestamp | 记录创建时间 |

说明：

```
VDrive 快照用于追溯当时扫描到的文件和文件夹。
它不是替代 VDrive 的文件管理系统。
```

---

# 10. 用户、权限与系统设置表

## 10.1 users：用户表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 用户ID |
| uid | varchar | 公司 UID |
| name | varchar | 用户姓名 |
| email | varchar | 公司邮箱 |
| status | varchar | 用户状态：active / disabled |
| password_hash | varchar | 密码哈希；如接统一认证可不存 |
| last_login_at | timestamp | 最近登录时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

status 枚举：

```
active
disabled
```

---

## 10.2 user_permissions：用户权限表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 权限记录ID |
| user_id | bigint / uuid | 用户ID |
| permission_code | varchar | 权限编码 |
| created_at | timestamp | 分配时间 |

permission_code 枚举：

```
inspection_engineer
rules_admin
project_admin
super_admin
```

---

## 10.3 system_settings：系统设置表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 设置ID |
| setting_key | varchar | 设置键 |
| setting_value_json | jsonb | 设置值 |
| updated_by | bigint / uuid | 最近修改人 |
| updated_at | timestamp | 最近修改时间 |

示例：

```
{
  "auto_check_enabled": true
}
```

---

# 11. 审计日志表

## 11.1 audit_logs：审计日志表

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| id | bigint / uuid | 日志ID |
| user_id | bigint / uuid | 操作人ID |
| action_type | varchar | 操作类型 |
| target_type | varchar | 操作对象类型 |
| target_id | bigint / uuid | 操作对象ID |
| before_json | jsonb | 操作前数据 |
| after_json | jsonb | 操作后数据 |
| ip_address | varchar | IP地址 |
| created_at | timestamp | 操作时间 |

必须记录的操作：

```
登录
创建任务
删除项目
启动自动检查
写入自动检查初判
选择候选文件
转人工判断
确认检查项
推翻自动检查初判
归档当前轮
标记整改完成
撤销整改完成
触发复查
关闭待跟进
更正报告
发布业务规则版本
修改自动检查执行规则
修改用户权限
修改系统设置
```

---

# 12. 状态字段审查

## 12.1 必须入库的状态字段

| 表 | 字段 | 原因 |
| --- | --- | --- |
| users | status | 账号启用/停用是管理员动作 |
| projects | status | 项目删除是软删除业务动作 |
| business_rule_versions | status | 规则版本生命周期 |
| inspection_tasks | status | 点检任务生命周期 |
| inspection_rounds | status | 轮次是否归档 |
| inspection_items | status | 检查项处理阶段 |
| auto_check_results | auto_status | 自动检查执行状态 |
| file_parse_jobs | status | 文件解析异步任务状态 |
| vdrive_scan_batches | scan_status | VDrive扫描异步任务状态 |

---

## 12.2 不入库、运行时推导的状态

| 对象 | 推导状态 | 推导字段 |
| --- | --- | --- |
| RectificationItem | 待整改 / 已超期 / 已完成 | planned_finish_date + marked_done_at |
| FollowUpItem | 待跟进 / 已超期 / 已落实 | planned_finish_date + closed_at |
| InspectionReport | 正常 / 已更正 | 是否存在 report_corrections |

---

# 13. 唯一约束建议

```
users.uid 唯一

qg_nodes.node_code 唯一

business_rule_versions:
qg_node_id + version_no 唯一

business_check_rules:
business_rule_version_id + rule_code 唯一

auto_check_execution_rules:
business_check_rule_id + execution_code 唯一

rule_snapshots:
inspection_task_id 唯一

inspection_rounds:
inspection_task_id + round_no 唯一

inspection_reports:
inspection_task_id 唯一

report_items:
report_id + source_rule_code 唯一

user_permissions:
user_id + permission_code 唯一
```

活跃任务唯一约束：

```
同一 project_id + qg_node_id 下，不允许同时存在 status in ('running', 'rectifying') 的 inspection_tasks。
```

PostgreSQL 可用部分唯一索引：

```
CREATE UNIQUE INDEX uq_active_task_per_project_node
ON inspection_tasks(project_id, qg_node_id)
WHERE status IN ('running', 'rectifying');
```

---

# 14. 索引建议

## 14.1 工作台查询

```
inspection_tasks(status, created_by)
inspection_tasks(status, project_id)
rectification_items(inspection_task_id, marked_done_at)
followup_items(project_id, closed_at, planned_finish_date)
```

## 14.2 档案查询

```
inspection_reports(project_id)
inspection_reports(qg_node_id)
inspection_reports(overall_result)
inspection_reports(last_modified_at)
projects(project_name)
project_models(model_name)
```

## 14.3 规则查询

```
business_rule_versions(qg_node_id, status)
business_check_rules(business_rule_version_id, sort_order)
auto_check_execution_rules(business_check_rule_id, is_enabled)
```

## 14.4 自动检查查询

```
auto_check_results(inspection_item_id, is_latest)
auto_check_candidate_files(auto_check_result_id)
file_parse_jobs(inspection_item_id, status)
vdrive_files(scan_batch_id, file_name)
vdrive_folders(scan_batch_id, folder_name)
```

---

# 15. 一期最小落表范围

一期建议必须落表：

```
users
user_permissions
system_settings

projects
project_orders
project_models

qg_nodes
business_rule_versions
business_check_rules
auto_check_execution_rules
rule_snapshots

inspection_tasks
inspection_rounds
inspection_items
engineer_decisions

auto_check_results
auto_check_candidate_files

rectification_items
followup_items

inspection_reports
report_items
report_corrections

vdrive_scan_batches
vdrive_folders
vdrive_files

audit_logs
```

可二期再落：

```
file_parse_jobs
prompt_templates
model_call_logs
```

说明：

```
如果一期只做文件存在性判断，file_parse_jobs 可以暂缓。
如果一期涉及 Excel 内容判断，file_parse_jobs 需要提前落表。
```

---

# 16. 数据库设计结论

本数据库设计固定以下核心结论：

```
1. Project 使用软删除，projects.status = deleted。
2. BusinessCheckRule 和 AutoCheckExecutionRule 分表。
3. BusinessCheckRule 用于业务展示、检查项生成和报告引用。
4. BusinessCheckRule 不保存文件定位、字眼匹配、候选策略、解析器、Prompt 或模型配置。
5. AutoCheckExecutionRule 用于后端真实自动检查执行。
6. 文件存在性判断基于 VDrive 文件元数据识别候选文件和判断是否满足要求。
7. 文件内容判断必须先完成文件存在性判断，确认目标文件后才下载并解析。
8. 系统直连判断通过 QMS / UCM 等外部系统接口执行。
9. InspectionTask 创建时冻结业务规则快照和自动检查执行规则快照。
10. InspectionItem 是业务规则快照生成出来的执行实例。
11. 一个 InspectionTask 只有一份 InspectionReport。
12. InspectionReport 是否更正由 ReportCorrection 推导，不存 status。
13. RectificationItem 和 FollowUpItem 不存 status。
14. VDrive 文件与文件夹保存扫描快照，而不是替代 VDrive 文件系统。
```

后续状态机设计、API 设计和自动检查执行架构均应以本数据库设计为基础。

# 16. Dashboard API

## 16.1 工作台概览

```
GET /api/v1/dashboard/overview
```

返回：

```
{
  "running_task_count": 12,
  "rectifying_task_count": 4,
  "completed_task_count": 38,
  "overdue_rectification_count": 3,
  "overdue_followup_count": 2,
  "candidate_waiting_count": 5,
  "manual_required_count": 8
}
```

---

## 16.2 我的待办

```
GET /api/v1/dashboard/my-todos
```

返回分类：

```
待确认检查项
待选择候选文件
待归档任务
待整改项
待跟进项
待复查任务
```

---

# 17. Audit Log API

## 17.1 审计日志列表

```
GET /api/v1/audit-logs
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| user_id | 操作人 |
| action_type | 操作类型 |
| target_type | 对象类型 |
| target_id | 对象ID |
| start_time | 开始时间 |
| end_time | 结束时间 |

权限：

```
super_admin
```

---

# 18. System Setting API

## 18.1 获取系统设置

```
GET /api/v1/system-settings
```

---

## 18.2 修改系统设置

```
PUT /api/v1/system-settings/{setting_key}
```

请求示例：

```
{
  "setting_value": {
    "auto_check_enabled": true
  }
}
```

系统动作：

```
1. 修改 system_settings。
2. 写入 audit_logs。
```

---

# 19. 关键错误码

## 19.1 项目错误

```
PROJECT_NOT_FOUND
PROJECT_DELETED
PROJECT_VDRIVE_LINK_INVALID
PROJECT_NAME_CONFIRM_FAILED
```

---

## 19.2 规则错误

```
RULE_VERSION_NOT_FOUND
NO_PUBLISHED_RULE_VERSION
AUTO_RULE_REQUIRED
RULE_VERSION_NOT_DRAFT
RULE_VERSION_ALREADY_PUBLISHED
```

---

## 19.3 点检任务错误

```
INSPECTION_TASK_NOT_FOUND
ACTIVE_TASK_ALREADY_EXISTS
INSPECTION_TASK_NOT_RUNNING
INSPECTION_TASK_NOT_RECTIFYING
INSPECTION_TASK_COMPLETED
INSPECTION_TASK_VOIDED
```

---

## 19.4 轮次错误

```
ROUND_NOT_FOUND
ROUND_ALREADY_ARCHIVED
ROUND_NOT_RUNNING
RUNNING_ROUND_ALREADY_EXISTS
```

---

## 19.5 检查项错误

```
INSPECTION_ITEM_NOT_FOUND
ITEM_NOT_CONFIRMABLE
ITEM_NOT_CANDIDATE_WAITING
ITEM_ALREADY_CONFIRMED
ITEM_AUTO_RULE_MISSING
ITEM_IN_ARCHIVED_ROUND
```

---

## 19.6 自动检查错误

```
AUTO_CHECK_FAILED
VDRIVE_SCAN_FAILED
NO_CANDIDATE_FILE
MULTIPLE_CANDIDATE_FILES
FILE_DOWNLOAD_FAILED
FILE_PARSE_FAILED
EXTERNAL_SYSTEM_ERROR
```

---

## 19.7 报告错误

```
REPORT_NOT_FOUND
REPORT_ITEM_NOT_FOUND
REPORT_CORRECTION_REASON_REQUIRED
REPORT_CORRECTION_NOT_ALLOWED
```

---

# 20. API 设计结论

本 API 设计固定以下结论：

```
1. API 按业务事件设计，不直接暴露数据库状态修改。
2. 创建点检任务必须生成规则快照、轮次、检查项和报告。
3. 自动检查项通过 StartAutoCheck 进入执行流程。
4. file_content 自动检查必须先完成 file_existence。
5. 多候选文件必须通过 SelectCandidateFile 决定后续执行。
6. 自动检查结果只是初判，最终结论必须通过 ConfirmInspectionItem。
7. 归档当前轮由 ArchiveCurrentRound 完成，并联动报告、整改项、待跟进项。
8. NO_GO 后进入 rectifying，整改完成后才能 TriggerRecheck。
9. C_GO 任务归档后 completed，但生成待跟进项。
10. 报告更正只影响报告层，不回写点检流程。
11. deleted 项目不允许新建任务，但历史数据保留。
12. 后续自动检查执行架构应围绕 AutoCheckExecutionRule、AutoCheckResult、CandidateFile、FileParseJob 展开。
```
