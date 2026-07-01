# CheckFlow 后端 API 设计 v0.1

## 1. 文档目的

本文档用于定义 CheckFlow 一期系统的后端 API 设计，包括接口分组、核心请求参数、返回结构、状态流转触发点、权限要求和异常处理原则。

本文档承接：

```
01. CheckFlow 领域模型设计 v1.0
02. CheckFlow 系统架构设计 v1.0
03. CheckFlow 数据库设计 v1.1
04. CheckFlow 状态机设计 v1.0
```

API 设计目标：

```
1. API 围绕业务事件设计，而不是直接暴露数据库 CRUD。
2. 状态字段不能通过普通 update 接口随意修改。
3. 所有关键操作必须触发状态机校验。
4. 自动检查结果只作为初判，最终结论由工程师确认接口产生。
5. 文件内容判断必须先完成文件存在性判断。
6. 报告更正不修改原始点检流程。
```

---

# 2. API 设计原则

## 2.1 统一前缀

```
/api/v1
```

示例：

```
POST /api/v1/inspection-tasks
```

---

## 2.2 统一返回结构

成功返回：

```
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

失败返回：

```
{
  "success": false,
  "error": {
    "code": "INSPECTION_TASK_NOT_RUNNING",
    "message": "当前任务不是进行中状态，无法归档",
    "details": {}
  }
}
```

---

## 2.3 分页结构

列表接口统一使用：

```
GET /api/v1/projects?page=1&page_size=20
```

返回：

```
{
  "success": true,
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 156
  },
  "message": "ok"
}
```

---

## 2.4 状态修改必须走业务动作接口

禁止：

```
PATCH /inspection-tasks/{id}
{
  "status": "completed"
}
```

必须：

```
POST /inspection-tasks/{id}/archive-current-round
```

说明：

```
状态变更必须经过业务事件、前置条件校验和联动数据生成。
```

---

## 2.5 权限控制原则

权限编码：

```
inspection_engineer    点检工程师
rules_admin            规则管理员
project_admin          项目管理员
super_admin            超级管理员
```

权限建议：

| 操作类型 | 需要权限 |
| --- | --- |
| 创建点检任务 | inspection_engineer |
| 自动检查 | inspection_engineer |
| 工程师确认 | inspection_engineer |
| 归档轮次 | inspection_engineer |
| 整改 / 复查 | inspection_engineer |
| 报告更正 | inspection_engineer |
| 项目删除 | project_admin |
| 规则配置 | rules_admin |
| 用户权限配置 | super_admin |

`super_admin` 仅代表账号和权限管理能力，不默认拥有业务数据范围或业务操作权限；如需执行业务操作，账号必须显式叠加对应业务权限。

---

# 3. API 分组总览

```
1. Auth API
2. User & Permission API
3. Project API
4. VDrive API
5. Rule API
6. Auto Check Execution Rule API
7. Inspection Task API
8. Inspection Item API
9. Auto Check API
10. Rectification API
11. Follow-up API
12. Report API
13. Dashboard API
14. Audit Log API
15. System Setting API
```

---

# 4. Auth API

## 4.1 登录

```
POST /api/v1/auth/login
```

请求：

```
{
  "uid": "10012345",
  "password": "******"
}
```

返回：

```
{
  "success": true,
  "data": {
    "access_token": "jwt_token",
    "token_type": "Bearer",
    "expires_in": 7200,
    "user": {
      "id": "u_001",
      "uid": "10012345",
      "name": "张三",
      "email": "zhangsan@example.com",
      "permissions": [
        "inspection_engineer"
      ]
    }
  },
  "message": "ok"
}
```

说明：

```
如果后续接入公司统一认证，本接口可以替换为 SSO 回调。
```

---

## 4.2 获取当前用户信息

```
GET /api/v1/auth/me
```

返回：

```
{
  "success": true,
  "data": {
    "id": "u_001",
    "uid": "10012345",
    "name": "张三",
    "email": "zhangsan@example.com",
    "status": "active",
    "permissions": [
      "inspection_engineer",
      "rules_admin"
    ]
  },
  "message": "ok"
}
```

---

# 5. User & Permission API

## 5.1 用户列表

```
GET /api/v1/users
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| keyword | 用户姓名、UID、邮箱 |
| status | active / disabled |
| page | 页码 |
| page_size | 每页数量 |

---

## 5.2 创建用户

```
POST /api/v1/users
```

请求：

```
{
  "uid": "10012345",
  "name": "张三",
  "email": "zhangsan@example.com",
  "permissions": [
    "inspection_engineer"
  ]
}
```

权限：

```
super_admin
```

---

## 5.3 更新用户权限

```
PUT /api/v1/users/{user_id}/permissions
```

请求：

```
{
  "permissions": [
    "inspection_engineer",
    "rules_admin"
  ]
}
```

系统动作：

```
1. 更新 user_permissions。
2. 写入 audit_logs。
```

---

## 5.4 启用 / 停用用户

```
POST /api/v1/users/{user_id}/enable
POST /api/v1/users/{user_id}/disable
```

说明：

```
users.status 是管理员动作状态，必须通过专用接口修改。
```

# 6. Project API

## 6.1 项目列表

```
GET /api/v1/projects
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| keyword | 项目名称、客户、机型 |
| qg_node_id | QG节点 |
| status | normal / deleted |
| mq_user_id | MQ工程师 |
| page | 页码 |
| page_size | 每页数量 |

默认规则：

```
普通列表默认只返回 status = normal 的项目。
deleted 项目仅管理员可查询。
```

---

## 6.2 项目详情

```
GET /api/v1/projects/{project_id}
```

返回内容：

```
{
  "id": "p_001",
  "project_name": "A项目",
  "customer": "客户A",
  "bu": "BU1",
  "mq_user": {
    "id": "u_001",
    "name": "张三"
  },
  "vdrive": {
    "url": "https://docs.xxx.com/indrive#/index?id=enterprise_xxx",
    "folder_guid": "922df4e1-d844-4bf7",
    "folder_id": 123456,
    "folder_name": "A项目资料"
  },
  "orders": [],
  "models": [],
  "status": "normal"
}
```

---

## 6.3 创建项目

```
POST /api/v1/projects
```

请求：

```
{
  "project_name": "A项目",
  "customer": "客户A",
  "project_category": "new_project",
  "bu": "BU1",
  "project_level": "A",
  "mq_user_id": "u_001",
  "mp_owner": "李四",
  "group_name": "第一组",
  "planned_mp_date": "2026-10-01",
  "production_line": "Line 1",
  "vdrive_url": "https://docs.xxx.com/indrive#/index?id=enterprise_922df4e1-d844-4bf7",
  "receive_date": "2026-06-30",
  "models": [
    "Model-A",
    "Model-B"
  ]
}
```

系统动作：

```
1. 校验 VDrive URL。
2. 解析 folderGuid。
3. 调用 VDrive 获取 folderId。
4. 创建 projects。
5. 创建 project_orders。
6. 创建 project_models。
7. 写入 audit_logs。
```

---

## 6.4 编辑项目基础信息

```
PATCH /api/v1/projects/{project_id}
```

允许修改：

```
project_name
customer
project_category
bu
project_level
mq_user_id
mp_owner
group_name
planned_mp_date
production_line
```

不建议通过此接口修改：

```
status
vdrive_folder_guid
vdrive_folder_id
deleted_at
deleted_by
```

VDrive 链接如需修改，使用专用接口。

---

## 6.5 修改项目 VDrive 链接

```
POST /api/v1/projects/{project_id}/vdrive-link
```

请求：

```
{
  "vdrive_url": "https://docs.xxx.com/indrive#/index?id=enterprise_xxx"
}
```

前置条件：

```
1. Project.status = normal。
2. 用户具备 project_admin 权限。
3. 新链接可解析 folderGuid。
4. 可通过 VDrive 接口获取 folderId。
```

系统动作：

```
1. 更新项目 VDrive URL。
2. 更新 folderGuid、folderId、folderName、folderPath。
3. 写入 audit_logs。
```

---

## 6.6 项目加单

```
POST /api/v1/projects/{project_id}/orders
```

请求：

```
{
  "receive_date": "2026-07-01",
  "models": [
    "Model-C",
    "Model-D"
  ]
}
```

系统动作：

```
1. 创建 project_orders。
2. 创建 project_models。
3. 写入 audit_logs。
```

---

## 6.7 删除项目

```
DELETE /api/v1/projects/{project_id}
```

请求：

```
{
  "confirm_project_name": "A项目",
  "delete_reason": "误建项目"
}
```

对应状态事件：

```
DeleteProject
```

系统动作：

```
1. projects.status = deleted。
2. 写入 deleted_by、deleted_at、delete_reason。
3. 普通列表不再展示。
4. 保留历史任务和报告。
5. 写入 audit_logs。
```

---

# 7. VDrive API

## 7.1 校验 VDrive 文件夹链接

```
POST /api/v1/vdrive/validate-folder-link
```

请求：

```
{
  "vdrive_url": "https://docs.xxx.com/indrive#/index?id=enterprise_922df4e1-d844-4bf7"
}
```

返回：

```
{
  "success": true,
  "data": {
    "valid": true,
    "folder_guid": "922df4e1-d844-4bf7",
    "folder_id": 123456,
    "folder_name": "A项目资料",
    "folder_path": "/项目资料/A项目"
  },
  "message": "ok"
}
```

说明：

```
该接口只做校验和预览，不创建项目。
```

---

## 7.2 扫描项目 VDrive 文件夹

```
POST /api/v1/projects/{project_id}/vdrive/scan
```

请求：

```
{
  "inspection_task_id": "t_001",
  "inspection_round_id": "r_001"
}
```

系统动作：

```
1. 创建 vdrive_scan_batches。
2. 调用 VDrive 获取文件夹和文件。
3. 写入 vdrive_folders。
4. 写入 vdrive_files。
5. 更新 scan_status。
```

---

## 7.3 获取扫描结果

```
GET /api/v1/vdrive/scan-batches/{scan_batch_id}
```

返回：

```
{
  "scan_batch_id": "scan_001",
  "scan_status": "success",
  "folders_count": 32,
  "files_count": 468,
  "started_at": "2026-06-30 10:00:00",
  "finished_at": "2026-06-30 10:02:31"
}
```

---

# 8. Rule API

## 8.1 QG 节点列表

```
GET /api/v1/qg-nodes
```

返回：

```
{
  "items": [
    {
      "id": "qg_001",
      "node_code": "QG3.3",
      "node_name": "QG3.3",
      "sort_order": 5,
      "is_active": true
    }
  ]
}
```

---

## 8.2 规则版本列表

```
GET /api/v1/business-rule-versions
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| qg_node_id | QG节点ID |
| status | draft / published / deprecated |

---

## 8.3 创建业务规则版本

```
POST /api/v1/business-rule-versions
```

请求：

```
{
  "qg_node_id": "qg_001",
  "version_no": "V03",
  "change_summary": "新增QG3.3检查项"
}
```

返回：

```
{
  "id": "brv_003",
  "status": "draft"
}
```

---

## 8.4 获取业务规则版本详情

```
GET /api/v1/business-rule-versions/{version_id}
```

返回内容包括：

```
业务规则版本信息
business_check_rules 列表
每条规则关联的 auto_check_execution_rules 简要信息
```

---

## 8.5 新增业务检查规则

```
POST /api/v1/business-rule-versions/{version_id}/business-check-rules
```

请求：

```
{
  "rule_code": "QG33_PFMEA_001",
  "item_name": "PFMEA",
  "item_type": "auto",
  "check_type": "file_existence",
  "checklist_requirement": "PFMEA文件已上传并在要求时间内更新",
  "owner_dept": "PT",
  "is_apqp": true,
  "sort_order": 10
}
```

说明：

```
business_check_rules 不保存文件定位、匹配字眼、候选策略、解析器、Prompt 或模型配置。
这些内容在 auto_check_execution_rules 中配置。
```

---

## 8.6 修改业务检查规则

```
PATCH /api/v1/business-check-rules/{rule_id}
```

允许修改：

```
item_name
item_type
check_type
checklist_requirement
owner_dept
is_apqp
is_active
sort_order
```

不允许修改：

```
rule_code
business_rule_version_id
```

---

## 8.7 发布业务规则版本

```
POST /api/v1/business-rule-versions/{version_id}/publish
```

对应事件：

```
PublishBusinessRuleVersion
```

前置条件：

```
1. business_rule_versions.status = draft。
2. 当前用户具备 rules_admin 权限。
3. 自动检查项必须配置可用的 auto_check_execution_rules。
4. 人工检查项不需要 auto_check_execution_rules。
5. 继承项不需要 auto_check_execution_rules。
```

系统动作：

```
1. 当前版本 status = published。
2. 同一 QG 节点下旧 published 版本改为 deprecated。
3. 写入 published_by、published_at。
4. 写入 audit_logs。
```

---

## 8.8 废弃规则版本

```
POST /api/v1/business-rule-versions/{version_id}/deprecate
```

说明：

```
废弃已发布版本不影响已创建任务。
已创建任务使用 rule_snapshots。
```

---

# 9. Auto Check Execution Rule API

## 9.1 创建自动检查执行规则

```
POST /api/v1/business-check-rules/{rule_id}/auto-check-execution-rules
```

请求示例：文件存在性判断

```
{
  "execution_code": "PFMEA_FILE_EXISTENCE_V1",
  "execution_mode": "file_existence",
  "adapter_type": "vdrive",
  "config_version": "V1",
  "is_enabled": true,
  "config_json": {
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
}
```

---

## 9.2 创建文件内容判断执行规则

```
POST /api/v1/business-check-rules/{rule_id}/auto-check-execution-rules
```

请求示例：

```
{
  "execution_code": "DFA_CONTENT_CHECK_V1",
  "execution_mode": "file_content",
  "adapter_type": "vdrive",
  "config_version": "V1",
  "is_enabled": true,
  "config_json": {
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
      "candidate_strategy": "by_check_item_config"
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
      "parse_failed": "manual_required"
    }
  }
}
```

说明：

```
file_content 类型必须先执行 file_existence。
未找到候选文件时，不创建下载和解析任务。
多候选文件时，必须先等待工程师选择候选文件。
```

---

## 9.3 创建系统直连执行规则

```
POST /api/v1/business-check-rules/{rule_id}/auto-check-execution-rules
```

请求示例：

```
{
  "execution_code": "PIL_QMS_CHECK_V1",
  "execution_mode": "system_direct",
  "adapter_type": "qms",
  "config_version": "V1",
  "is_enabled": true,
  "config_json": {
    "execution_mode": "system_direct",
    "system_direct": {
      "adapter": "qms",
      "query_type": "pil_by_model",
      "model_source": "project_models",
      "validation": {
        "min_close_rate": 80
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
}
```

---

## 9.4 修改自动检查执行规则

```
PATCH /api/v1/auto-check-execution-rules/{execution_rule_id}
```

说明：

```
修改自动检查执行规则只影响后续新建任务。
已创建任务使用 rule_snapshots 中的 auto_check_execution_rule_snapshot_json。
```

---

## 9.5 启用 / 停用自动检查执行规则

```
POST /api/v1/auto-check-execution-rules/{execution_rule_id}/enable
POST /api/v1/auto-check-execution-rules/{execution_rule_id}/disable
```

---

# 10. Inspection Task API

## 10.1 创建点检任务

```
POST /api/v1/inspection-tasks
```

对应事件：

```
CreateInspectionTask
```

请求：

```
{
  "project_id": "p_001",
  "qg_node_id": "qg_003"
}
```

前置条件：

```
1. Project.status = normal。
2. 项目存在有效 VDrive folderGuid 和 folderId。
3. QG 节点存在 published 业务规则版本。
4. 同一 project_id + qg_node_id 下不存在 running / rectifying 任务。
```

系统动作：

```
1. 创建 inspection_tasks，status = running。
2. 创建 rule_snapshots。
3. 创建首轮 inspection_rounds。
4. 根据业务规则快照生成 inspection_items。
5. 初始化 inspection_reports。
6. 投递自动检查任务。
7. 写入 audit_logs。
```

返回：

```
{
  "inspection_task_id": "t_001",
  "project_id": "p_001",
  "qg_node_id": "qg_003",
  "status": "running",
  "current_round_no": 1,
  "round_id": "r_001",
  "report_id": "rep_001"
}
```

---

## 10.2 点检任务列表

```
GET /api/v1/inspection-tasks
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| project_id | 项目ID |
| qg_node_id | QG节点 |
| status | running / rectifying / completed / voided |
| mq_user_id | MQ工程师 |
| page | 页码 |
| page_size | 每页数量 |

---

## 10.3 点检任务详情

```
GET /api/v1/inspection-tasks/{task_id}
```

返回内容：

```
{
  "id": "t_001",
  "status": "running",
  "current_round_no": 1,
  "project": {},
  "qg_node": {},
  "current_round": {},
  "summary": {
    "total_items": 32,
    "confirmed_count": 20,
    "pending_count": 12,
    "candidate_waiting_count": 2,
    "manual_required_count": 3
  }
}
```

---

## 10.4 获取当前轮检查项

```
GET /api/v1/inspection-tasks/{task_id}/current-round/items
```

返回：

```
{
  "round_id": "r_001",
  "round_no": 1,
  "items": [
    {
      "id": "item_001",
      "source_rule_code": "QG33_PFMEA_001",
      "item_name": "PFMEA",
      "item_type": "auto",
      "check_type": "file_existence",
      "checklist_requirement": "PFMEA文件已上传并在要求时间内更新",
      "owner_dept": "PT",
      "is_apqp": true,
      "status": "auto_completed",
      "final_result": null,
      "latest_auto_result": {
        "auto_status": "success",
        "auto_result": "pass",
        "evidence_text": "已找到PFMEA文件，修改时间满足要求"
      },
      "engineer_decision": null
    }
  ]
}
```

---

## 10.5 归档当前轮

```
POST /api/v1/inspection-tasks/{task_id}/archive-current-round
```

对应事件：

```
ArchiveCurrentRound
```

前置条件：

```
1. InspectionTask.status = running。
2. 当前 InspectionRound.status = running。
3. 当前轮所有检查项均已 confirmed 或 inherited。
4. 不存在 pending / checking / candidate_waiting / auto_completed / manual_required 的未确认项。
```

返回：

```
{
  "inspection_task_id": "t_001",
  "archived_round_no": 1,
  "overall_result": "NO_GO",
  "task_status": "rectifying",
  "generated_rectification_count": 3,
  "generated_followup_count": 0,
  "report_id": "rep_001"
}
```

---

## 10.6 触发复查

```
POST /api/v1/inspection-tasks/{task_id}/trigger-recheck
```

对应事件：

```
TriggerRecheck
```

前置条件：

```
1. InspectionTask.status = rectifying。
2. 最新轮次 status = archived。
3. 所有整改项 marked_done_at 不为空。
4. 当前不存在 running 轮次。
```

返回：

```
{
  "inspection_task_id": "t_001",
  "task_status": "running",
  "new_round_id": "r_002",
  "new_round_no": 2,
  "generated_items_count": 3
}
```

---

## 10.7 作废点检任务

```
POST /api/v1/inspection-tasks/{task_id}/void
```

请求：

```
{
  "void_reason": "任务误建，QG节点选择错误"
}
```

对应事件：

```
VoidInspectionTask
```

返回：

```
{
  "inspection_task_id": "t_001",
  "status": "voided",
  "voided_at": "2026-06-30 12:00:00"
}
```

---

# 11. Inspection Item API

## 11.1 检查项详情

```
GET /api/v1/inspection-items/{item_id}
```

返回内容：

```
检查项快照信息
最新自动检查结果
候选文件
工程师确认记录
历史过程记录
```

---

## 11.2 启动自动检查

```
POST /api/v1/inspection-items/{item_id}/auto-check
```

对应事件：

```
StartAutoCheck
```

适用状态：

```
pending
manual_required
```

前置条件：

```
1. InspectionTask.status = running。
2. InspectionRound.status = running。
3. InspectionItem.check_type_snapshot in ('file_existence', 'file_content', 'system_direct')。
4. 存在 auto_check_execution_rule_snapshot。
```

返回：

```
{
  "inspection_item_id": "item_001",
  "status": "checking",
  "auto_check_job_id": "job_001"
}
```

---

## 11.3 选择候选文件

```
POST /api/v1/inspection-items/{item_id}/candidate-files/select
```

对应事件：

```
SelectCandidateFile
```

请求：

```
{
  "candidate_file_id": "cf_001"
}
```

前置条件：

```
1. InspectionItem.status = candidate_waiting。
2. 候选文件属于当前检查项最新 AutoCheckResult。
```

系统动作：

```
1. 标记候选文件为 selected。
2. 如果是 file_existence，重新生成自动检查结果。
3. 如果是 file_content，下载并解析该文件。
4. 更新 inspection_items.status。
```

---

## 11.4 转人工判断

```
POST /api/v1/inspection-items/{item_id}/convert-to-manual
```

请求：

```
{
  "reason": "候选文件无法确认，转人工判断"
}
```

对应事件：

```
ConvertToManual
```

返回：

```
{
  "inspection_item_id": "item_001",
  "status": "manual_required"
}
```

---

## 11.5 确认检查项

```
POST /api/v1/inspection-items/{item_id}/confirm
```

对应事件：

```
ConfirmInspectionItem
```

请求：满足

```
{
  "decision_result": "pass",
  "decision_text": "文件已确认，满足要求"
}
```

请求：不满足

```
{
  "decision_result": "fail",
  "decision_text": "未找到有效PFMEA文件",
  "responsible_owner": "PT",
  "planned_finish_date": "2026-07-15"
}
```

请求：带条件满足

```
{
  "decision_result": "conditional",
  "decision_text": "文件已提交，但部分内容需补充",
  "countermeasure": "补充特殊特性管控措施",
  "responsible_owner": "PT",
  "planned_finish_date": "2026-07-10"
}
```

请求：不适用

```
{
  "decision_result": "na",
  "decision_text": "该项目不涉及此项内容"
}
```

系统动作：

```
1. 创建 engineer_decisions。
2. 更新 inspection_items.final_result。
3. inspection_items.status = confirmed。
4. 判断是否推翻自动检查结果。
5. 写入 audit_logs。
```

---

# 12. Auto Check API

## 12.1 获取自动检查结果

```
GET /api/v1/inspection-items/{item_id}/auto-check-results
```

返回：

```
{
  "items": [
    {
      "id": "acr_001",
      "attempt_no": 1,
      "is_latest": true,
      "auto_status": "candidate_waiting",
      "auto_result": "manual_required",
      "evidence_text": "发现多个候选文件，需要工程师确认",
      "candidate_files": []
    }
  ]
}
```

---

## 12.2 获取候选文件列表

```
GET /api/v1/inspection-items/{item_id}/candidate-files
```

返回：

```
{
  "items": [
    {
      "id": "cf_001",
      "file_name": "PFMEA_V3.xlsx",
      "file_path": "/A项目/QG3.3/PFMEA/PFMEA_V3.xlsx",
      "file_version": "V3",
      "file_size": 203456,
      "created_time": "2026-06-01 09:00:00",
      "modified_time": "2026-06-25 18:00:00",
      "recommend_score": 0.92,
      "recommend_reason": "文件名和路径匹配度较高，修改时间最新",
      "is_selected": false
    }
  ]
}
```

---

## 12.3 重新自动检查

```
POST /api/v1/inspection-items/{item_id}/auto-check/retry
```

说明：

```
重试会生成新的 auto_check_results，attempt_no + 1，旧结果 is_latest = false。
```

适用场景：

```
VDrive 临时异常
规则调整后重新执行当前任务
工程师手动要求重跑
```

---

# 13. Rectification API

## 13.1 整改项列表

```
GET /api/v1/rectification-items
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| inspection_task_id | 点检任务ID |
| project_id | 项目ID |
| overdue | 是否超期 |
| done | 是否已完成 |

说明：

```
整改项不存 status。
overdue / done 由 planned_finish_date 和 marked_done_at 推导。
```

---

## 13.2 标记整改完成

```
POST /api/v1/rectification-items/{item_id}/mark-done
```

对应事件：

```
MarkRectificationDone
```

前置条件：

```
1. InspectionTask.status = rectifying。
2. RectificationItem.marked_done_at 为空。
```

返回：

```
{
  "rectification_item_id": "rect_001",
  "marked_done_at": "2026-07-10 10:00:00"
}
```

---

## 13.3 撤销整改完成

```
POST /api/v1/rectification-items/{item_id}/reopen
```

对应事件：

```
ReopenRectificationItem
```

前置条件：

```
1. InspectionTask.status = rectifying。
2. RectificationItem.marked_done_at 不为空。
3. 尚未触发复查。
```

---

# 14. Follow-up API

## 14.1 待跟进项列表

```
GET /api/v1/followup-items
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| inspection_task_id | 点检任务ID |
| project_id | 项目ID |
| overdue | 是否超期 |
| closed | 是否已落实 |

说明：

```
待跟进项不存 status。
overdue / closed 由 planned_finish_date 和 closed_at 推导。
```

---

## 14.2 关闭待跟进项

```
POST /api/v1/followup-items/{item_id}/close
```

请求：

```
{
  "close_note": "后续措施已落实"
}
```

对应事件：

```
CloseFollowUpItem
```

系统动作：

```
1. 写入 closed_by。
2. 写入 closed_at。
3. 写入 audit_logs。
```

说明：

```
关闭待跟进项不改变 InspectionTask.status。
C_GO 任务在归档时已经 completed。
```

---

# 15. Report API

## 15.1 报告列表

```
GET /api/v1/reports
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| project_id | 项目ID |
| qg_node_id | QG节点 |
| overall_result | FULL_GO / C_GO / NO_GO |
| corrected | 是否已更正 |
| page | 页码 |
| page_size | 每页数量 |

说明：

```
corrected 不来自 inspection_reports.status。
系统通过是否存在 report_corrections 推导。
```

---

## 15.2 报告详情

```
GET /api/v1/reports/{report_id}
```

返回内容：

```
{
  "id": "rep_001",
  "inspection_task_id": "t_001",
  "project": {},
  "qg_node": {},
  "overall_result": "NO_GO",
  "latest_round_no": 1,
  "corrected": false,
  "summary": {},
  "items": [
    {
      "id": "ri_001",
      "item_name": "PFMEA",
      "checklist_requirement": "PFMEA文件已上传并在要求时间内更新",
      "final_result": "fail",
      "auto_result_snapshot": {},
      "engineer_decision_snapshot": {},
      "process_records": []
    }
  ]
}
```

---

## 15.3 报告更正

```
POST /api/v1/reports/{report_id}/items/{report_item_id}/correct
```

对应事件：

```
CorrectReportItem
```

请求：

```
{
  "after_result": "pass",
  "correction_reason": "归档后确认资料已在归档前补充，原报告结论需更正"
}
```

系统动作：

```
1. 创建 report_corrections。
2. 更新 report_items.final_result。
3. 重新计算 inspection_reports.overall_result。
4. 更新 inspection_reports.last_modified_at。
5. 写入 audit_logs。
```

重要边界：

```
1. 不修改 InspectionItem。
2. 不修改 EngineerDecision。
3. 不修改 AutoCheckResult。
4. 不重新生成整改项。
5. 不重新生成待跟进项。
6. 不改变 InspectionTask.status。
```

---

## 15.4 导出报告

```
GET /api/v1/reports/{report_id}/export
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| format | pdf / docx / xlsx |

返回：

```
{
  "download_url": "https://xxx/report.docx"
}
```
