# CheckFlow 状态机设计 v0.1

## 1. 文档目的

本文档用于定义 CheckFlow 系统中核心业务对象的状态、状态流转、触发事件、前置条件、联动动作和禁止操作。

本文档承接：

```
01. CheckFlow 领域模型设计 v1.0
02. CheckFlow 系统架构设计 v1.0
03. CheckFlow 数据库设计 v1.1
```

状态机设计目标：

```
1. 明确哪些状态需要入库，哪些状态运行时推导。
2. 明确每个状态由什么业务事件触发。
3. 明确状态变更前的校验条件。
4. 明确状态变更后的联动数据生成。
5. 为后续 API 设计提供依据。
```

---

# 2. 状态机设计原则

## 2.1 状态不能随意改，只能由业务事件驱动

系统中不允许直接通过普通更新接口修改状态字段。

例如：

```
不允许直接 update inspection_tasks.status = completed
```

必须通过业务事件触发：

```
ArchiveCurrentRound
  → 计算节点结论
  → 更新 InspectionRound
  → 更新 InspectionTask
  → 更新 InspectionReport
```

---

## 2.2 可推导状态不入库

以下对象不保存 status：

```
RectificationItem
FollowUpItem
InspectionReport
```

它们的展示状态运行时推导。

---

## 2.3 自动检查结果不是最终结论

自动检查只产生初判：

```
AutoCheckResult
```

最终结论来自：

```
EngineerDecision
```

因此：

```
自动检查结果不能直接决定节点通过。
自动检查结果不能直接生成报告最终结论。
自动检查结果必须经过工程师确认。
```

---

## 2.4 归档是关键业务边界

一轮点检归档后：

```
InspectionRound.status = archived
```

该轮次下的检查项、工程师确认、自动检查结果原则上不再修改。

归档后如需修正，只能通过：

```
ReportCorrection
```

进行报告更正。

---

## 2.5 文件内容判断必须先完成文件存在性判断

文件内容判断不是独立执行。

```
file_content = file_existence + file_download + file_parse + content_validation
```

也就是说：

```
先找到目标文件
再下载文件
再解析内容
再执行内容判断
```

如果没有找到候选文件，不能进入下载和解析。

---

# 3. Project 状态机

## 3.1 状态定义

```
normal      正常
deleted     已删除，软删除
```

---

## 3.2 状态流转

```
normal
  └── DeleteProject
        ↓
      deleted
```

---

## 3.3 DeleteProject：删除项目

### 触发场景

用户在项目管理或工作台中删除项目。

### 前置条件

```
1. Project.status = normal。
2. 当前用户具备 project_admin 或 super_admin 权限。
3. 用户完成二次确认。
4. 若前端要求输入项目名称，则输入内容必须与项目名称一致。
```

### 系统动作

```
1. projects.status = deleted。
2. 写入 deleted_by、deleted_at、delete_reason。
3. 普通项目列表、工作台列表、档案入口不再展示该项目。
4. 项目下的点检任务、轮次、检查项、报告、整改项、待跟进项、自动检查结果全部保留。
5. 写入 audit_logs。
```

### 禁止动作

```
1. deleted 项目不能新建点检任务。
2. deleted 项目不能加单。
3. deleted 项目不能修改基础信息。
4. deleted 项目历史报告仍允许管理员查看。
```

---

# 4. InspectionTask 状态机

## 4.1 状态定义

```
running       点检进行中
rectifying    整改中
completed     节点完成
voided        已作废
```

---

## 4.2 状态流转总览

```
CreateInspectionTask
      ↓
   running
      │
      ├── ArchiveCurrentRound：FULL_GO / C_GO
      │       ↓
      │    completed
      │
      ├── ArchiveCurrentRound：NO_GO
      │       ↓
      │    rectifying
      │
      ├── VoidInspectionTask
      │       ↓
      │    voided
      │
      └── 整改完成后 TriggerRecheck
              ↑
          rectifying
```

更完整的循环：

```
running
  └── ArchiveCurrentRound：NO_GO
        ↓
      rectifying
        └── TriggerRecheck
              ↓
            running
              └── ArchiveCurrentRound
                    ├── FULL_GO / C_GO → completed
                    └── NO_GO → rectifying
```

---

## 4.3 CreateInspectionTask：创建点检任务

### 触发场景

用户选择项目和 QG 节点，创建点检任务。

### 前置条件

```
1. Project.status = normal。
2. 当前项目已配置有效 VDrive 文件夹链接。
3. VDrive 链接可以解析出 folderGuid。
4. folderGuid 可以通过 VDrive 接口换取 folderId。
5. 当前 QG 节点存在 published 状态的业务规则版本。
6. 同一个 project_id + qg_node_id 下不存在 running 或 rectifying 状态的任务。
```

### 系统动作

```
1. 创建 inspection_tasks，status = running。
2. 创建 rule_snapshots。
3. 冻结 business_rule_snapshot_json。
4. 冻结 auto_check_execution_rule_snapshot_json。
5. 创建 inspection_rounds，round_no = 1，status = running。
6. 根据业务规则快照生成 inspection_items。
7. 自动检查项初始 status = pending。
8. 人工检查项初始 status = manual_required。
9. 继承项初始 status = inherited，final_result = inherit。
10. 创建或初始化 inspection_reports。
11. 投递自动检查任务。
12. 写入 audit_logs。
```

### 注意

```
InspectionItem 来自业务规则快照，不直接依赖当前规则表。
后续规则修改不影响已创建任务。
```

---

## 4.4 ArchiveCurrentRound：归档当前轮

### 触发场景

工程师完成当前轮所有检查项确认后，点击归档。

### 前置条件

```
1. InspectionTask.status = running。
2. 当前 InspectionRound.status = running。
3. 当前轮所有检查项均已完成。
4. 检查项完成条件：
   - status = confirmed；或
   - status = inherited。
5. 不存在 checking 状态的自动检查项。
6. 不存在 candidate_waiting 状态的检查项。
7. 不存在 pending 状态的自动检查项。
```

### 节点结论计算规则

按当前轮工程师最终结论计算：

```
只要存在 fail：
  overall_result = NO_GO

不存在 fail，但存在 conditional：
  overall_result = C_GO

全部为 pass / na / inherit：
  overall_result = FULL_GO
```

### 系统动作

当结论为 FULL_GO：

```
1. inspection_rounds.status = archived。
2. inspection_rounds.archived_at = 当前时间。
3. inspection_tasks.status = completed。
4. inspection_tasks.completed_at = 当前时间。
5. inspection_tasks.archived_at = 当前时间。
6. 更新 inspection_reports.overall_result = FULL_GO。
7. 更新 inspection_reports.latest_round_no。
8. 创建或更新 report_items。
9. 追加 report_items.process_records_json。
10. 写入 audit_logs。
```

当结论为 C_GO：

```
1. inspection_rounds.status = archived。
2. inspection_tasks.status = completed。
3. 更新 inspection_reports.overall_result = C_GO。
4. 创建或更新 report_items。
5. 追加 process_records_json。
6. 根据 conditional 检查项生成 followup_items。
7. 写入 audit_logs。
```

当结论为 NO_GO：

```
1. inspection_rounds.status = archived。
2. inspection_tasks.status = rectifying。
3. 更新 inspection_reports.overall_result = NO_GO。
4. 创建或更新 report_items。
5. 追加 process_records_json。
6. 根据 fail 检查项生成 rectification_items。
7. 写入 audit_logs。
```

---

## 4.5 TriggerRecheck：触发复查

### 触发场景

NO-GO 后，责任人完成整改，点检工程师发起复查。

### 前置条件

```
1. InspectionTask.status = rectifying。
2. 当前最新 InspectionRound.status = archived。
3. 当前任务下所有未关闭整改项均已 marked_done_at 不为空。
4. 不存在进行中的复查轮次。
```

### 系统动作

```
1. 新建 inspection_rounds。
2. round_no = inspection_tasks.current_round_no + 1。
3. status = running。
4. inspection_tasks.status = running。
5. inspection_tasks.current_round_no = 新 round_no。
6. 根据上一轮 fail 检查项生成新一轮 inspection_items。
7. 新生成的自动检查项 status = pending。
8. 新生成的人工检查项 status = manual_required。
9. 投递自动检查任务。
10. 写入 audit_logs。
```

### 注意

```
复查轮默认只复查上一轮 fail 项。
上一轮 pass、conditional、na、inherit 项不重复生成复查项。
```

---

## 4.6 VoidInspectionTask：作废任务

### 触发场景

任务误建、项目节点选错、业务上不应继续执行。

### 前置条件

```
1. InspectionTask.status in ('running', 'rectifying')。
2. 当前用户具备 inspection_engineer 或 super_admin 权限。
3. 用户填写作废原因。
```

### 系统动作

```
1. inspection_tasks.status = voided。
2. 写入 voided_by、voided_at、void_reason。
3. 终止尚未执行的自动检查任务。
4. 当前页面不再允许确认检查项、归档、整改、复查。
5. 保留已有检查项、自动检查结果、工程师确认和审计日志。
6. 写入 audit_logs。
```

### 禁止动作

```
completed 任务原则上不允许作废。
如确需修正 completed 任务，只能通过报告更正。
```

# 5. InspectionRound 状态机

## 5.1 状态定义

```
running     当前轮正在执行
archived    当前轮已归档
```

---

## 5.2 状态流转

```
CreateInspectionTask / TriggerRecheck
      ↓
   running
      ↓
ArchiveCurrentRound
      ↓
   archived
```

---

## 5.3 规则约束

```
1. 一个 InspectionTask 同一时间只能有一个 running 轮次。
2. archived 轮次不可直接修改。
3. archived 轮次下的 InspectionItem 不可重新确认。
4. archived 轮次下的 AutoCheckResult 不可重跑。
5. 如果需要修正报告，只能通过 ReportCorrection。
```

---

# 6. InspectionItem 状态机

## 6.1 状态定义

```
pending             待自动检查
checking            自动检查中
candidate_waiting   等待候选文件选择
auto_completed      自动检查完成，待工程师确认
manual_required     需要人工判断
confirmed           工程师已确认
inherited           已继承
```

---

## 6.2 状态流转总览

```
自动检查项：

pending
  ↓ StartAutoCheck
checking
  ├── 自动检查成功
  │       ↓
  │   auto_completed
  │       ↓ ConfirmInspectionItem
  │   confirmed
  │
  ├── 多候选文件
  │       ↓
  │   candidate_waiting
  │       ↓ SelectCandidateFile
  │   checking
  │
  └── 无法自动判断
          ↓
      manual_required
          ↓ ConfirmInspectionItem
      confirmed
```

```
人工检查项：

manual_required
  ↓ ConfirmInspectionItem
confirmed
```

```
继承项：

inherited
```

---

## 6.3 创建检查项时的初始状态

| 检查项类型 | check_type | 初始状态 |
| --- | --- | --- |
| 自动检查项 | file_existence | pending |
| 自动检查项 | file_content | pending |
| 系统直连项 | system_direct | pending |
| 人工检查项 | manual | manual_required |
| 继承项 | inherit | inherited |

说明：

```
人工检查项不进入自动检查流程。
继承项不需要工程师重复确认，归档时视为已完成项。
```

---

## 6.4 StartAutoCheck：启动自动检查

### 触发场景

任务创建后自动触发，或工程师点击重新自动检查。

### 前置条件

```
1. InspectionTask.status = running。
2. InspectionRound.status = running。
3. InspectionItem.status = pending 或 manual_required。
4. InspectionItem.check_type_snapshot in ('file_existence', 'file_content', 'system_direct')。
5. 当前检查项存在可用的 auto_check_execution_rule_snapshot。
```

### 系统动作

```
1. inspection_items.status = checking。
2. 创建自动检查执行任务。
3. 根据 check_type_snapshot 进入对应执行链路。
4. 写入 audit_logs。
```

### 异常处理

```
如果自动检查项缺少执行规则：
  inspection_items.status = manual_required
  auto_check_results.auto_status = manual_required
  auto_check_results.auto_result = manual_required
```

---

## 6.5 file_existence：文件存在性判断状态流转

### 执行链路

```
扫描 VDrive
  ↓
基于文件名称、文件路径、文件版本、创建时间、修改时间、文件大小识别候选文件
  ↓
判断候选文件数量和可信度
```

### 结果 1：找到明确目标文件

系统动作：

```
1. 创建 auto_check_results。
2. auto_status = success。
3. auto_result = pass 或 suspect。
4. 写入 evidence_text。
5. 写入 auto_check_candidate_files。
6. inspection_items.status = auto_completed。
```

### 结果 2：未找到候选文件

系统动作：

```
1. 创建 auto_check_results。
2. auto_status = manual_required。
3. auto_result = not_found。
4. evidence_text 记录未找到文件。
5. inspection_items.status = manual_required。
```

说明：

```
未找到文件不直接判定最终不满足。
工程师可能知道文件在其他位置，因此进入人工判断。
```

### 结果 3：存在多个候选文件

系统动作：

```
1. 创建 auto_check_results。
2. auto_status = candidate_waiting。
3. auto_result = manual_required。
4. 写入多个 auto_check_candidate_files。
5. inspection_items.status = candidate_waiting。
```

### 结果 4：VDrive 扫描失败

系统动作：

```
1. 创建 auto_check_results。
2. auto_status = manual_required。
3. auto_result = error。
4. 写入 error_code、error_message。
5. inspection_items.status = manual_required。
```

---

## 6.6 file_content：文件内容判断状态流转

### 核心原则

文件内容判断必须先完成文件存在性判断。

```
file_content
  = 文件存在性判断
  + 文件下载
  + 文件解析
  + 内容判断
```

### 执行链路

```
扫描 VDrive
  ↓
文件存在性判断
  ↓
确认目标文件
  ↓
下载文件
  ↓
按 parser_rule_code 解析文件
  ↓
按 validation_rule_code 判断内容
  ↓
生成自动检查初判
```

### 结果 1：前置文件存在性判断未找到候选文件

系统动作：

```
1. auto_check_results.auto_status = manual_required。
2. auto_check_results.auto_result = not_found。
3. inspection_items.status = manual_required。
4. 不创建 file_parse_jobs。
```

### 结果 2：前置文件存在性判断出现多个候选文件

系统动作：

```
1. auto_check_results.auto_status = candidate_waiting。
2. auto_check_results.auto_result = manual_required。
3. 创建 auto_check_candidate_files。
4. inspection_items.status = candidate_waiting。
5. 暂不下载文件。
6. 暂不创建 file_parse_jobs。
```

### 结果 3：找到明确目标文件，下载解析成功

系统动作：

```
1. 创建 auto_check_candidate_files。
2. 创建 file_parse_jobs。
3. 下载文件。
4. 解析文件。
5. 执行内容判断。
6. 创建 auto_check_results。
7. auto_status = success。
8. auto_result = pass / fail / suspect。
9. inspection_items.status = auto_completed。
```

### 结果 4：下载失败

系统动作：

```
1. file_parse_jobs.status = failed。
2. auto_check_results.auto_status = manual_required。
3. auto_check_results.auto_result = error。
4. inspection_items.status = manual_required。
```

### 结果 5：解析失败

系统动作：

```
1. file_parse_jobs.status = failed。
2. auto_check_results.auto_status = manual_required。
3. auto_check_results.auto_result = error。
4. inspection_items.status = manual_required。
```

### 结果 6：文件类型不支持

系统动作：

```
1. auto_check_results.auto_status = manual_required。
2. auto_check_results.auto_result = error。
3. inspection_items.status = manual_required。
```

---

## 6.7 system_direct：系统直连判断状态流转

### 执行链路

```
读取项目 / 机型 / QG节点参数
  ↓
调用 QMS / UCM 等外部系统接口
  ↓
获取结构化数据
  ↓
执行判断规则
  ↓
生成自动检查初判
```

### 结果 1：系统查询成功

系统动作：

```
1. 创建 auto_check_results。
2. auto_status = success。
3. auto_result = pass / fail / suspect。
4. inspection_items.status = auto_completed。
```

### 结果 2：外部系统无数据

系统动作：

```
1. auto_check_results.auto_status = manual_required。
2. auto_result = manual_required。
3. inspection_items.status = manual_required。
```

### 结果 3：外部系统异常

系统动作：

```
1. auto_check_results.auto_status = manual_required。
2. auto_result = error。
3. 写入 error_code、error_message。
4. inspection_items.status = manual_required。
```

---

## 6.8 SelectCandidateFile：选择候选文件

### 触发场景

自动检查发现多个候选文件，工程师选择一个文件继续检查。

### 前置条件

```
1. InspectionItem.status = candidate_waiting。
2. InspectionTask.status = running。
3. InspectionRound.status = running。
4. 用户选择的 candidate_file 属于当前 inspection_item 的最新 auto_check_result。
```

### 系统动作

```
1. 更新 auto_check_candidate_files.is_selected。
2. inspection_items.status = checking。
3. 如果 check_type = file_existence：
   - 重新生成自动检查结果；
   - inspection_items.status = auto_completed。
4. 如果 check_type = file_content：
   - 下载被选中的文件；
   - 创建 file_parse_jobs；
   - 执行解析和内容判断；
   - 成功后 inspection_items.status = auto_completed；
   - 失败后 inspection_items.status = manual_required。
5. 写入 audit_logs。
```

---

## 6.9 ConvertToManual：转人工判断

### 触发场景

工程师不选择候选文件，或者认为自动检查无法处理，需要人工确认。

### 前置条件

```
1. InspectionItem.status in ('candidate_waiting', 'checking', 'auto_completed')。
2. InspectionTask.status = running。
3. InspectionRound.status = running。
```

### 系统动作

```
1. inspection_items.status = manual_required。
2. 记录转人工原因。
3. 写入 audit_logs。
```

---

## 6.10 ConfirmInspectionItem：确认检查项

### 触发场景

工程师确认某个检查项的最终结果。

### 前置条件

```
1. InspectionTask.status = running。
2. InspectionRound.status = running。
3. InspectionItem.status in ('auto_completed', 'manual_required')。
4. 当前用户具备 inspection_engineer 权限。
```

### 根据最终结论校验必填字段

当 decision_result = pass：

```
decision_text 可选。
```

当 decision_result = fail：

```
decision_text 必填。
responsible_owner 必填。
planned_finish_date 必填。
```

当 decision_result = conditional：

```
countermeasure 必填。
responsible_owner 必填。
planned_finish_date 必填。
```

当 decision_result = na：

```
decision_text 必填。
```

### 系统动作

```
1. 创建 engineer_decisions。
2. 更新 inspection_items.final_result。
3. inspection_items.status = confirmed。
4. 如工程师结论与自动检查初判不一致，override_auto_result = true。
5. 写入 audit_logs。
```

# 7. AutoCheckResult 状态机

## 7.1 状态定义

```
success              自动检查成功
failed               自动检查失败
candidate_waiting    等待候选文件选择
manual_required      需要人工处理
```

---

## 7.2 状态说明

| auto_status | 含义 | 对 InspectionItem 的影响 |
| --- | --- | --- |
| success | 自动检查完成 | inspection_items.status = auto_completed |
| failed | 自动检查异常失败 | inspection_items.status = manual_required |
| candidate_waiting | 多候选文件待确认 | inspection_items.status = candidate_waiting |
| manual_required | 无法自动判断 | inspection_items.status = manual_required |

---

## 7.3 auto_result 定义

```
pass              自动初判满足
fail              自动初判不满足
not_found         未找到候选文件
suspect           自动检查结果不确定
manual_required   需要人工判断
error             执行异常
```

说明：

```
auto_result 只作为初判和依据展示。
最终结果以 engineer_decisions.decision_result 为准。
```

---

# 8. RectificationItem 推导状态与业务动作

## 8.1 不入库 status

整改项不保存 status。

展示状态由以下字段推导：

```
planned_finish_date
marked_done_at
```

---

## 8.2 状态推导规则

```
待整改：
  marked_done_at 为空
  且 planned_finish_date >= 当前日期

已超期：
  marked_done_at 为空
  且 planned_finish_date < 当前日期

已完成：
  marked_done_at 不为空
  且 marked_done_at <= planned_finish_date

逾期完成：
  marked_done_at 不为空
  且 marked_done_at > planned_finish_date
```

---

## 8.3 GenerateRectificationItems：生成整改项

### 触发场景

当前轮归档结论为 NO_GO。

### 前置条件

```
1. ArchiveCurrentRound 计算结果为 NO_GO。
2. 当前轮存在 decision_result = fail 的检查项。
```

### 系统动作

```
1. 为每个 fail 检查项生成 rectification_items。
2. source_round_id = 当前轮次ID。
3. source_item_id = 当前检查项ID。
4. problem_desc 来自 engineer_decisions.decision_text。
5. responsible_owner 来自 engineer_decisions.responsible_owner。
6. planned_finish_date 来自 engineer_decisions.planned_finish_date。
7. inspection_tasks.status = rectifying。
```

---

## 8.4 MarkRectificationDone：标记整改完成

### 触发场景

责任方完成整改后，点检工程师或责任人标记完成。

### 前置条件

```
1. InspectionTask.status = rectifying。
2. RectificationItem.marked_done_at 为空。
```

### 系统动作

```
1. 写入 marked_done_by。
2. 写入 marked_done_at。
3. 写入 audit_logs。
```

### 注意

```
标记整改完成不会自动触发复查。
只有所有整改项完成后，才允许 TriggerRecheck。
```

---

## 8.5 ReopenRectificationItem：撤销整改完成

### 触发场景

整改误标记完成，或发现整改资料不完整。

### 前置条件

```
1. InspectionTask.status = rectifying。
2. RectificationItem.marked_done_at 不为空。
3. 尚未触发复查。
```

### 系统动作

```
1. 清空 marked_done_by。
2. 清空 marked_done_at。
3. 写入 audit_logs。
```

---

# 9. FollowUpItem 推导状态与业务动作

## 9.1 不入库 status

待跟进项不保存 status。

展示状态由以下字段推导：

```
planned_finish_date
closed_at
```

---

## 9.2 状态推导规则

```
待跟进：
  closed_at 为空
  且 planned_finish_date >= 当前日期

已超期：
  closed_at 为空
  且 planned_finish_date < 当前日期

已落实：
  closed_at 不为空
  且 closed_at <= planned_finish_date

逾期落实：
  closed_at 不为空
  且 closed_at > planned_finish_date
```

---

## 9.3 GenerateFollowUpItems：生成待跟进项

### 触发场景

当前轮归档结论为 C_GO。

### 前置条件

```
1. ArchiveCurrentRound 计算结果为 C_GO。
2. 当前轮存在 decision_result = conditional 的检查项。
```

### 系统动作

```
1. 为每个 conditional 检查项生成 followup_items。
2. source_round_id = 当前轮次ID。
3. source_item_id = 当前检查项ID。
4. countermeasure 来自 engineer_decisions.countermeasure。
5. responsible_owner 来自 engineer_decisions.responsible_owner。
6. planned_finish_date 来自 engineer_decisions.planned_finish_date。
7. inspection_tasks.status = completed。
```

---

## 9.4 CloseFollowUpItem：关闭待跟进项

### 触发场景

带条件满足项的后续措施已落实。

### 前置条件

```
1. FollowUpItem.closed_at 为空。
2. 当前用户具备 inspection_engineer 或 super_admin 权限。
```

### 系统动作

```
1. 写入 closed_by。
2. 写入 closed_at。
3. 写入 audit_logs。
```

### 注意

```
关闭待跟进项不改变 InspectionTask.status。
C_GO 任务在归档时已经 completed。
```

---

# 10. InspectionReport 生成、更新与更正规则

## 10.1 报告不保存 status

报告是否更正由以下规则推导：

```
存在 report_corrections：
  已更正

不存在 report_corrections：
  正常
```

---

## 10.2 报告生成时机

报告在以下场景创建或初始化：

```
CreateInspectionTask
```

也可以在第一次归档时创建。

推荐策略：

```
任务创建时创建 inspection_reports。
第一次归档时写入完整 report_items。
```

---

## 10.3 归档时更新报告

每次 ArchiveCurrentRound 后，系统更新报告。

### 首轮归档

```
1. 创建或更新 inspection_reports。
2. 生成 report_items。
3. report_items.latest_inspection_item_id 指向首轮检查项。
4. 写入 auto_result_snapshot。
5. 写入 engineer_decision_snapshot。
6. 写入 final_result。
7. 初始化 process_records_json。
8. 更新 inspection_reports.overall_result。
9. 更新 latest_round_no = 1。
```

### 复查轮归档

```
1. 查找对应 source_rule_code 的 report_items。
2. 更新 latest_inspection_item_id。
3. 更新 auto_result_snapshot。
4. 更新 engineer_decision_snapshot。
5. 更新 final_result。
6. 向 process_records_json 追加本轮过程记录。
7. 更新 inspection_reports.overall_result。
8. 更新 latest_round_no = 当前 round_no。
```

---

## 10.4 process_records_json 结构建议

```
[
  {
    "round_no": 1,
    "inspection_item_id": "xxx",
    "auto_result": "not_found",
    "engineer_result": "fail",
    "decision_text": "未找到有效PFMEA文件",
    "responsible_owner": "PT",
    "planned_finish_date": "2026-07-15",
    "decided_by": "张三",
    "decided_at": "2026-06-30 10:30:00"
  },
  {
    "round_no": 2,
    "inspection_item_id": "yyy",
    "auto_result": "pass",
    "engineer_result": "pass",
    "decision_text": "复查确认文件已补充",
    "decided_by": "张三",
    "decided_at": "2026-07-18 14:20:00"
  }
]
```

---

## 10.5 CorrectReportItem：报告更正

### 触发场景

报告归档后，发现报告明细需要修正。

### 前置条件

```
1. inspection_reports 已存在。
2. report_items 已存在。
3. 当前用户具备 inspection_engineer 或 super_admin 权限。
4. 用户填写 correction_reason。
```

### 系统动作

```
1. 创建 report_corrections。
2. 记录 before_result。
3. 记录 after_result。
4. 更新 report_items.final_result。
5. 重新计算 inspection_reports.overall_result。
6. 更新 inspection_reports.last_modified_at。
7. 写入 audit_logs。
```

### 重要边界

```
报告更正不修改 InspectionItem。
报告更正不修改 EngineerDecision。
报告更正不修改 AutoCheckResult。
报告更正不重新生成整改项。
报告更正不重新生成待跟进项。
报告更正不改变 InspectionTask.status。
```

说明：

```
报告更正是报告层面的修正，不是重新打开任务流程。
```

---

# 11. 核心业务事件清单

## 11.1 项目事件

```
DeleteProject
```

---

## 11.2 任务事件

```
CreateInspectionTask
ArchiveCurrentRound
TriggerRecheck
VoidInspectionTask
```

---

## 11.3 检查项事件

```
StartAutoCheck
SelectCandidateFile
ConvertToManual
ConfirmInspectionItem
```

---

## 11.4 自动检查事件

```
RunFileExistenceCheck
RunFileContentCheck
RunSystemDirectCheck
WriteAutoCheckResult
```

---

## 11.5 整改和跟进事件

```
GenerateRectificationItems
MarkRectificationDone
ReopenRectificationItem
GenerateFollowUpItems
CloseFollowUpItem
```

---

## 11.6 报告事件

```
GenerateOrUpdateReport
CorrectReportItem
```

---

# 12. 权限控制建议

| 事件 | 建议权限 |
| --- | --- |
| CreateInspectionTask | inspection_engineer / super_admin |
| StartAutoCheck | inspection_engineer / super_admin |
| SelectCandidateFile | inspection_engineer / super_admin |
| ConvertToManual | inspection_engineer / super_admin |
| ConfirmInspectionItem | inspection_engineer / super_admin |
| ArchiveCurrentRound | inspection_engineer / super_admin |
| MarkRectificationDone | inspection_engineer / super_admin |
| ReopenRectificationItem | inspection_engineer / super_admin |
| TriggerRecheck | inspection_engineer / super_admin |
| CloseFollowUpItem | inspection_engineer / super_admin |
| CorrectReportItem | inspection_engineer / super_admin |
| VoidInspectionTask | inspection_engineer / super_admin |
| DeleteProject | project_admin / super_admin |
| PublishBusinessRuleVersion | rules_admin / super_admin |
| UpdateAutoCheckExecutionRule | rules_admin / super_admin |

---

# 13. 状态机约束清单

## 13.1 任务约束

```
1. 同一 project_id + qg_node_id 下，不能同时存在 running / rectifying 任务。
2. voided 任务不能继续操作。
3. completed 任务不能重新打开，只能更正报告。
4. deleted 项目不能创建新任务。
```

---

## 13.2 轮次约束

```
1. 一个任务同一时间只能有一个 running 轮次。
2. archived 轮次不能修改检查项和工程师确认。
3. 复查只能从 rectifying 状态触发。
4. 复查前必须完成所有整改项。
```

---

## 13.3 检查项约束

```
1. pending 只能进入 checking 或 manual_required。
2. checking 只能由自动检查任务推进。
3. candidate_waiting 必须选择候选文件或转人工。
4. auto_completed 和 manual_required 可以进入 confirmed。
5. confirmed 后不可修改。
6. inherited 不参与自动检查，也不需要人工确认。
```

---

## 13.4 自动检查约束

```
1. file_content 必须先完成 file_existence。
2. file_content 未找到候选文件时不能下载。
3. file_content 多候选时不能下载，必须先选择候选文件。
4. 下载失败、解析失败、外部系统异常均进入 manual_required。
5. 自动检查结果不直接作为最终结论。
```

---

## 13.5 报告约束

```
1. 一个 InspectionTask 只有一份 InspectionReport。
2. InspectionReport 不绑定 InspectionRound。
3. 多轮记录进入 report_items.process_records_json。
4. 报告更正只影响报告，不影响任务流程。
5. 报告更正不重新生成整改项或待跟进项。
```

---

# 14. 后续 API 映射

后续 API 设计应以业务事件为中心，而不是以表 CRUD 为中心。

建议 API 映射：

```
POST   /inspection-tasks
       → CreateInspectionTask

POST   /inspection-items/{id}/auto-check
       → StartAutoCheck

POST   /inspection-items/{id}/candidate-files/select
       → SelectCandidateFile

POST   /inspection-items/{id}/convert-to-manual
       → ConvertToManual

POST   /inspection-items/{id}/confirm
       → ConfirmInspectionItem

POST   /inspection-tasks/{id}/archive-current-round
       → ArchiveCurrentRound

POST   /rectification-items/{id}/mark-done
       → MarkRectificationDone

POST   /rectification-items/{id}/reopen
       → ReopenRectificationItem

POST   /inspection-tasks/{id}/trigger-recheck
       → TriggerRecheck

POST   /followup-items/{id}/close
       → CloseFollowUpItem

POST   /reports/{id}/items/{item_id}/correct
       → CorrectReportItem

POST   /inspection-tasks/{id}/void
       → VoidInspectionTask

DELETE /projects/{id}
       → DeleteProject
```

---

# 15. 状态机设计结论

本状态机设计固定以下核心结论：

```
1. InspectionTask 是主流程状态机。
2. InspectionRound 是归档边界。
3. InspectionItem 是自动检查与人工确认的连接点。
4. AutoCheckResult 只是初判，不是最终结论。
5. 文件内容判断必须先做文件存在性判断。
6. NO_GO 归档后进入 rectifying。
7. 整改完成后才能触发复查。
8. C_GO 归档后任务 completed，但生成待跟进项。
9. FULL_GO 归档后任务 completed。
10. 报告更正不改变任务流程状态。
11. 可推导状态不入库。
12. 后续 API 应围绕业务事件设计，而不是直接暴露数据库 CRUD。
```