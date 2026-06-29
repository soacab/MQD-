# CheckFlow 领域模型设计 v1.0

## 1. 文档目的

本文档用于定义 CheckFlow 的核心领域对象、对象边界、对象关系、生命周期归属和职责边界。

本文档优先于数据库设计、状态机设计和 API 设计。

核心目标是回答：

```
1. 系统里有哪些核心对象？
2. 每个对象代表什么业务含义？
3. 每个对象由谁拥有？
4. 每个对象的生命周期跟谁一致？
5. 哪些对象是模板，哪些对象是实例？
6. 哪些对象是业务规则，哪些对象是 AI 执行规则？
7. 哪些状态需要入库，哪些状态运行时推导？
```

---

# 2. 总体领域结构

CheckFlow 的核心领域分为六个部分：

```
Project Domain          项目域
Inspection Domain       点检域
Rule Domain             规则域
AI Execution Domain     AI执行域
Report Domain           报告域
User & Permission Domain 用户与权限域
```

整体关系：

```
Project
  └── InspectionTask
        ├── InspectionRound
        │     └── InspectionItem
        │           ├── AICheckResult
        │           ├── AICandidateFile
        │           └── EngineerDecision
        │
        ├── InspectionReport
        │     └── ReportItem
        │           └── ReportCorrection
        │
        ├── RectificationItem
        └── FollowUpItem

BusinessRuleVersion
  └── BusinessCheckRule
        └── AIExecutionRule

InspectionTask
  └── RuleSnapshot
        ├── BusinessRuleSnapshot
        └── AIExecutionRuleSnapshot
```

---

# 3. 领域建模原则

## 3.1 模板与实例分离

系统中有两类对象：

```
模板对象：用于配置和复用
实例对象：用于某一次真实业务执行
```

例如：

```
BusinessCheckRule 是模板。
InspectionItem 是实例。

AIExecutionRule 是模板。
AICheckResult 是执行结果实例。
```

模板修改不能影响已经生成的实例。

---

## 3.2 业务规则与 AI 执行规则分离

规则分为两层：

```
Business Rule：业务规则
AI Execution Rule：AI执行规则
```

二者不能混用。

业务规则面向工程师和报告展示：

```
检查项名称
Checklist要求
业务点检位置
业务点检字眼
责任方
APQP标识
展示顺序
```

AI 执行规则面向系统后台和 AI 执行：

```
文件夹定位策略
文件匹配策略
排除规则
文件类型限制
候选文件排序策略
解析器配置
Prompt配置
模型配置
异常降级策略
```

业务规则回答：

```
工程师要检查什么？
报告里展示什么？
```

AI执行规则回答：

```
系统具体怎么找文件、读文件、判断文件？
```

---

## 3.3 快照优先

点检任务创建时，必须生成规则快照。

快照包含：

```
BusinessRuleSnapshot
AIExecutionRuleSnapshot
```

原因：

```
1. 规则发布后不能影响进行中任务。
2. 复查时应沿用任务创建时的规则口径。
3. 历史报告必须能追溯当时使用的规则。
4. AI判断结果必须能解释当时的执行逻辑。
```

---

## 3.4 数据库存事实，展示状态运行时推导

状态分两类。

第一类：必须入库的业务生命周期状态。

```
User.status
Project.status
RuleVersion.status
InspectionTask.status
InspectionRound.status
InspectionItem.status
AICheckResult.ai_status
FileParseJob.status
```

这些状态由明确业务动作触发，无法仅通过时间字段稳定推导。

第二类：不入库的展示状态。

```
RectificationItem：待整改 / 已超期 / 已完成
FollowUpItem：待跟进 / 已超期 / 已落实
InspectionReport：正常 / 已更正
```

这些可以由事实字段推导。

例如：

```
整改项已完成 = marked_done_at 不为空
整改项已超期 = marked_done_at 为空，且 planned_finish_date 已过

待跟进已落实 = closed_at 不为空
待跟进已超期 = closed_at 为空，且 planned_finish_date 已过

报告已更正 = 存在 ReportCorrection
```

---

# 4. Project Domain：项目域

## 4.1 Project

业务含义：

```
Project 是项目基础信息的承载对象，也是点检任务和历史报告的归属对象。
```

拥有对象：

```
ProjectOrder
ProjectModel
InspectionTask
```

核心字段概念：

```
项目名称
客户
项目类别
BU
项目等级
对应MP
MQ人员
小组
计划量产时间
生产线体
VDrive文件夹链接
VDrive folderGuid
VDrive folderId
```

生命周期：

```
normal → deleted
```

说明：

```
页面上的“删除项目”是软删除。
删除后项目不在普通工作台和档案列表展示。
项目下的任务、报告、AI结果、整改、待跟进、审计记录均保留。
```

所有者：

```
Project 是 ProjectOrder、ProjectModel、InspectionTask 的拥有者。
```

---

## 4.2 ProjectOrder

业务含义：

```
项目接收批次，用于记录项目接收时间和加单批次。
```

所属对象：

```
Project
```

生命周期：

```
跟随 Project。
```

说明：

```
一个项目可以有多个接收批次。
```

---

## 4.3 ProjectModel

业务含义：

```
项目机型记录。
```

所属对象：

```
ProjectOrder
```

生命周期：

```
跟随 ProjectOrder。
```

说明：

```
一个接收批次可以包含多个机型。
PIL 点检等系统直连项需要按机型逐一判断。
```

---

# 5. Rule Domain：规则域

## 5.1 BusinessRuleVersion

业务含义：

```
某个 QG 节点下的一版业务检查规则集合。
```

拥有对象：

```
BusinessCheckRule
```

生命周期：

```
draft → published → deprecated
```

职责：

```
管理某个 QG 节点下业务检查项的版本发布。
```

说明：

```
发布后的版本只影响新建点检任务。
历史任务不读取实时规则，只读取任务创建时的规则快照。
```

---

## 5.2 BusinessCheckRule

业务含义：

```
业务检查项模板。
```

它回答：

```
这个 QG 节点需要检查什么？
工程师在页面上看到什么？
报告里引用什么？
```

典型字段：

```
检查项编码
检查项名称
检查项类型
检查方式
Checklist要求
业务点检位置
业务点检字眼
责任方
是否APQP内容
展示顺序
是否启用
```

检查项类型：

```
AI自动检查项
人工检查项
系统直连项
继承项
```

说明：

```
BusinessCheckRule 中的业务点检位置、业务点检字眼，只用于工程师理解、点检页面展示、报告引用。
它们不是 AI 实际执行规则。
```

拥有关系：

```
BusinessCheckRule 属于 BusinessRuleVersion。
BusinessCheckRule 可以关联一个或多个 AIExecutionRule。
```

---

## 5.3 AIExecutionRule

业务含义：

```
AI 或系统自动检查的真实执行配置。
```

它回答：

```
系统具体如何找文件？
如何筛选候选文件？
如何解析文件？
如何调用 Prompt 或模型？
如何降级为人工？
```

典型字段：

```
关联业务检查项
执行类型
适配器类型
解析器类型
执行配置 JSON
Prompt模板
模型配置
是否启用
```

示例：

```yaml
target_folder_match:
  suffix_keywords: ["PFMEA"]

file_match:
  include_keywords: ["PFMEA"]
  exclude_keywords: ["archive", "old", "bak"]
  allowed_ext: [".xlsx", ".xls"]

selection_strategy:
  sort_by:
    - modified_time desc
    - file_size desc

validation:
  modified_within_days: 60

fallback:
  multiple_candidates: candidate_waiting
  no_file: manual_required
```

说明：

```
AIExecutionRule 面向系统后台、开发或算法配置。
不一定开放给点检工程师。
不直接出现在正式报告中，但其快照可用于追溯 AI 初判依据。
```

---

## 5.4 RuleSnapshot

业务含义：

```
点检任务创建时，对业务规则和 AI 执行规则的冻结副本。
```

包含：

```
BusinessRuleSnapshot
AIExecutionRuleSnapshot
```

所属对象：

```
InspectionTask
```

生命周期：

```
跟随 InspectionTask。
```

职责：

```
确保任务执行、复查、报告归档和历史追溯不受后续规则修改影响。
```

---

# 6. Inspection Domain：点检域

## 6.1 InspectionTask

业务含义：

```
一个项目在一个 QG 节点下的一次完整点检任务。
```

拥有对象：

```
InspectionRound
InspectionReport
RectificationItem
FollowUpItem
RuleSnapshot
```

职责：

```
控制一个 QG 节点点检任务的完整生命周期。
```

生命周期：

```
running → rectifying → running → completed
running / rectifying → voided
```

说明：

```
InspectionTask 是点检域的聚合根。
状态流转必须通过 InspectionTask 控制。
外部不能直接修改 Round、Item、Report 的关键状态。
```

---

## 6.2 InspectionRound

业务含义：

```
某个点检任务下的第 N 轮点检执行。
```

拥有对象：

```
InspectionItem
```

所属对象：

```
InspectionTask
```

生命周期：

```
running → archived
```

职责：

```
记录一轮点检执行过程。
归档后不可直接修改。
```

说明：

```
一个 InspectionTask 可以有多轮 InspectionRound。
round_no 表示第几轮。
不需要 round_type，因为首轮和复查轮可通过 round_no 推导。
```

---

## 6.3 InspectionItem

业务含义：

```
某一轮点检中的实际检查项实例。
```

来源：

```
由 BusinessCheckRule 快照生成。
```

所属对象：

```
InspectionRound
```

关联对象：

```
AICheckResult
AICandidateFile
EngineerDecision
```

职责：

```
记录该检查项在本轮中的处理状态和最终结论。
```

生命周期：

```
pending
→ checking
→ candidate_waiting / ai_completed / manual_required
→ confirmed

或：

pending → inherited
```

说明：

```
InspectionItem 是实例，不是规则。
BusinessCheckRule 修改后，不影响已经生成的 InspectionItem。
```

---

## 6.4 EngineerDecision

业务含义：

```
工程师对某个检查项实例给出的最终判断。
```

所属对象：

```
InspectionItem
```

职责：

```
记录最终结论、判断说明、责任人、对策、计划完成时间、是否推翻 AI。
```

说明：

```
工程师最终结论才参与归档和节点结果计算。
AI 初判不直接决定节点结果。
```

---

## 6.5 RectificationItem

业务含义：

```
由不满足项生成的整改跟踪对象。
```

来源：

```
某一轮 InspectionItem.final_result = fail。
```

所属对象：

```
InspectionTask
```

关键事实字段：

```
问题描述
责任人
计划完成时间
标记完成人
标记完成时间
```

状态推导：

```
待整改 = marked_done_at 为空，且 planned_finish_date 未过
已超期 = marked_done_at 为空，且 planned_finish_date 已过
已完成 = marked_done_at 不为空
```

说明：

```
RectificationItem 不存 status。
全部整改项完成后，才允许触发下一轮复查。
```

---

## 6.6 FollowUpItem

业务含义：

```
由带条件满足项生成的后续跟进对象。
```

来源：

```
某一轮 InspectionItem.final_result = conditional。
```

所属对象：

```
InspectionTask
```

关键事实字段：

```
对策
责任人
计划完成时间
标记落实人
标记落实时间
```

状态推导：

```
待跟进 = closed_at 为空，且 planned_finish_date 未过
已超期 = closed_at 为空，且 planned_finish_date 已过
已落实 = closed_at 不为空
```

说明：

```
FollowUpItem 不存 status。
带条件满足项不阻断节点完成，不进入整改复查流程。
```

---

# 7. AI Execution Domain：AI 执行域

## 7.1 AICheckTask

业务含义：

```
一次后台自动检查任务。
```

说明：

```
AICheckTask 可以是队列任务，不一定作为独立业务表长期存在。
如需要追踪异步执行过程，可作为 file_parse_jobs 或 ai_jobs 存储。
```

职责：

```
根据 InspectionItem 和 AIExecutionRuleSnapshot 执行自动检查。
```

输入：

```
InspectionItem
AIExecutionRuleSnapshot
Project上下文
VDrive folderId
机型列表
```

输出：

```
AICheckResult
AICandidateFile
```

---

## 7.2 AICheckResult

业务含义：

```
AI 或系统自动检查产生的初判结果。
```

所属对象：

```
InspectionItem
```

职责：

```
记录 AI 初判、判断依据、数据来源、异常原因、原始返回。
```

状态：

```
success
failed
candidate_waiting
manual_required
```

说明：

```
AICheckResult 是初判，不是最终业务结论。
```

---

## 7.3 AICandidateFile

业务含义：

```
自动检查过程中识别出的候选文件。
```

所属对象：

```
AICheckResult
```

职责：

```
记录候选文件、推荐原因、推荐分数、是否被工程师选择。
```

来源：

```
系统扫描
工程师手动补充
```

---

## 7.4 FileObject / FolderObject

业务含义：

```
VDrive 文件和文件夹在 CheckFlow 内部的标准化对象。
```

说明：

```
业务系统不直接使用 VDrive 原始字段。
VDriveAdapter 负责将 VDrive 接口结果转换为 FolderObject 和 FileObject。
```

---

# 8. Report Domain：报告域

## 8.1 InspectionReport

业务含义：

```
一个 InspectionTask 对应的一份节点报告。
```

所属对象：

```
InspectionTask
```

拥有对象：

```
ReportItem
ReportCorrection
```

职责：

```
汇总该任务所有轮次的点检结果。
展示当前最终结论和多轮过程记录。
```

说明：

```
一个任务只有一份报告。
报告不绑定单个轮次。
latest_round_no 表示当前报告汇总到第几轮。
```

报告是否更正：

```
通过是否存在 ReportCorrection 推导。
不需要 inspection_reports.status。
```

---

## 8.2 ReportItem

业务含义：

```
报告中的检查项明细。
```

来源：

```
按 BusinessCheckRule / InspectionItem 汇总生成。
```

职责：

```
展示某个检查项的当前最终结论和多轮过程记录。
```

说明：

```
每个检查项在报告中通常只有一条 ReportItem。
多轮点检记录进入 process_records。
```

---

## 8.3 ReportCorrection

业务含义：

```
报告明细的人工更正记录。
```

所属对象：

```
ReportItem
```

职责：

```
记录更正前结论、更正后结论、更正原因、更正人、更正时间。
```

说明：

```
更正不覆盖 AI 原始结论。
更正不删除原始过程记录。
更正只追加记录。
```

---

# 9. User & Permission Domain：用户与权限域

## 9.1 User

业务含义：

```
CheckFlow 系统中的用户。
```

说明：

```
UID 来自公司账号体系。
CheckFlow 维护用户在本产品内的状态和权限。
```

状态：

```
active
disabled
```

状态说明：

```
active / disabled 是管理员动作，必须入库。
```

---

## 9.2 Permission

业务含义：

```
用户在 CheckFlow 内的操作权限。
```

权限类型：

```
inspection_engineer
rules_admin
project_admin
super_admin
```

说明：

```
权限可叠加。
权限管理员不默认具备点检执行、项目管理或规则管理权限。
```

---

# 10. 核心领域事件

## 10.1 CreateInspectionTask

业务含义：

```
创建一个项目在某个 QG 节点下的点检任务。
```

核心动作：

```
1. 校验 Project。
2. 校验 VDrive 文件夹链接。
3. 读取当前已发布 BusinessRuleVersion。
4. 读取关联 AIExecutionRule。
5. 生成 BusinessRuleSnapshot。
6. 生成 AIExecutionRuleSnapshot。
7. 创建 InspectionTask。
8. 创建第 1 轮 InspectionRound。
9. 根据 BusinessRuleSnapshot 生成 InspectionItem。
10. 根据 AIExecutionRuleSnapshot 投递自动检查任务。
```

---

## 10.2 ArchiveCurrentRound

业务含义：

```
归档当前轮点检结果。
```

核心动作：

```
1. 校验当前轮所有 InspectionItem 已确认。
2. 汇总 EngineerDecision。
3. 计算 FULL-GO / C-GO / NO-GO。
4. 更新 InspectionRound 为 archived。
5. 更新 InspectionReport。
6. 更新 ReportItem.process_records。
7. 生成 RectificationItem 或 FollowUpItem。
8. 更新 InspectionTask 状态。
```

---

## 10.3 TriggerRecheck

业务含义：

```
整改项全部完成后，触发下一轮复查。
```

核心动作：

```
1. 校验当前任务处于 rectifying。
2. 校验当前来源轮次所有整改项已完成。
3. 创建下一轮 InspectionRound。
4. 仅为上一轮 fail 项生成新的 InspectionItem。
5. 投递自动检查任务。
6. InspectionTask 回到 running。
```

---

## 10.4 CorrectReportItem

业务含义：

```
授权用户对报告明细进行更正。
```

核心动作：

```
1. 写入 ReportCorrection。
2. 更新 ReportItem 当前最终结论。
3. 重新计算报告综合结论。
4. 保留原始过程记录。
```

---

## 10.5 DeleteProject

业务含义：

```
项目管理用户删除项目。
```

核心动作：

```
1. Project.status = deleted。
2. 普通列表不再展示。
3. 历史任务、报告、AI结果、审计记录均保留。
```

---

# 11. 对象关系稳定性判断

以下关系视为稳定，不应轻易调整：

```
Project 拥有 InspectionTask。
InspectionTask 拥有 InspectionRound。
InspectionRound 拥有 InspectionItem。
InspectionTask 拥有 InspectionReport。
InspectionTask 拥有 RectificationItem。
InspectionTask 拥有 FollowUpItem。
BusinessRuleVersion 拥有 BusinessCheckRule。
BusinessCheckRule 关联 AIExecutionRule。
InspectionTask 拥有 RuleSnapshot。
InspectionReport 拥有 ReportItem。
ReportItem 拥有 ReportCorrection。
```

以下关系明确不成立：

```
InspectionReport 不属于 InspectionRound。
InspectionItem 不属于 BusinessCheckRule。
AIExecutionRule 不直接属于 InspectionTask。
RectificationItem 不属于 InspectionRound，但记录来源轮次。
FollowUpItem 不属于 InspectionRound，但记录来源轮次。
```

---

# 12. 领域模型结论

CheckFlow 的核心聚合是：

```
Project
BusinessRuleVersion
InspectionTask
InspectionReport
User
```

其中最核心的是：

```
InspectionTask
```

InspectionTask 是点检业务的主聚合根，控制：

```
轮次
检查项
整改
复查
待跟进
报告归档
```

BusinessRule 和 AIExecutionRule 必须分层：

```
BusinessRule 用于业务展示和报告引用。
AIExecutionRule 用于后台真实执行。
```

点检任务创建时必须冻结两类规则快照：

```
BusinessRuleSnapshot
AIExecutionRuleSnapshot
```

后续数据库、状态机、API、AI执行架构均应基于本领域模型展开。