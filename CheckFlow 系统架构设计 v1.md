# CheckFlow 系统架构设计 v1.0

## 1. 文档目的

本文档用于说明 CheckFlow 的整体软件架构、分层方式、核心服务、外部系统接入、AI 执行子系统和关键业务时序。

本文档基于：

```
01. CheckFlow 领域模型设计 v1.0
```

本文档回答：

```
1. 领域对象如何在系统中运行？
2. 哪些服务负责哪些领域对象？
3. 业务规则、AI执行规则、点检任务、报告之间如何协作？
4. VDrive / QMS / UCM / LLM 等外部能力如何接入？
5. 创建任务、归档、复查、AI检查的核心链路如何执行？
```

---

# 2. 系统定位

CheckFlow 是面向 MQD QG 点检业务的企业级 AI 辅助点检系统。

系统主流程不是 AI 对话，而是：

```
项目 → 点检任务 → 点检轮次 → 检查项 → 工程师确认 → 归档报告 → 整改 / 复查
```

AI 在系统中的定位是：

```
辅助执行检查项的初步判断。
```

AI 不负责：

```
不直接决定最终结论。
不直接决定节点是否通过。
不直接归档报告。
不绕过工程师确认。
不修改业务规则。
```

系统负责：

```
业务对象管理
规则快照
点检任务状态流转
AI自动检查调度
工程师最终确认
整改复查
报告归档
全过程审计追溯
```

---

# 3. 总体架构

CheckFlow 采用分层架构：

```
Presentation Layer      前端展示层
        ↓
Application Layer       应用服务层
        ↓
Domain Layer            领域模型层
        ↓
Infrastructure Layer    基础设施层
```

整体结构：

```
Web Frontend
  ↓
REST API / WebSocket
  ↓
Application Services
  ├── ProjectService
  ├── RuleService
  ├── InspectionService
  ├── AIExecutionService
  ├── ReportService
  ├── UserService
  └── AdminService
  ↓
Domain Model
  ├── Project
  ├── BusinessRuleVersion
  ├── BusinessCheckRule
  ├── AIExecutionRule
  ├── InspectionTask
  ├── InspectionRound
  ├── InspectionItem
  ├── InspectionReport
  ├── RectificationItem
  └── FollowUpItem
  ↓
Infrastructure
  ├── PostgreSQL
  ├── Redis
  ├── Object Storage
  ├── Task Queue
  ├── VDrive Adapter
  ├── QMS Adapter
  ├── UCM Adapter
  ├── LLM Provider
  └── OCR / Parser
```

---

# 4. Presentation Layer：前端展示层

## 4.1 职责

前端负责：

```
页面展示
表单输入
操作触发
状态呈现
权限显隐
进度展示
结果查看
```

前端不负责：

```
不直接修改数据库状态
不直接调用 VDrive / QMS / UCM
不直接调用 LLM
不自行计算节点结论
不绕过后端状态机
```

## 4.2 主要页面

```
LoginPage                 登录页
WorkbenchPage             工作台
CreateInspectionTaskModal 新建点检任务弹窗
InspectionExecutionPage   点检执行页
RectificationPage         整改追踪页
ReportListPage            检查档案页
ReportDetailPage          报告详情页
BusinessRulePage          业务规则配置页
AdminPage                 后台管理页
```

## 4.3 前端交互原则

前端调用的是业务事件 API，而不是状态修改 API。

推荐：

```
POST /inspection-tasks/{id}/archive-current-round
POST /inspection-items/{id}/confirm
POST /inspection-tasks/{id}/trigger-recheck
```

不推荐：

```
POST /tasks/{id}/update-status
```

---

# 5. Application Layer：应用服务层

应用服务层负责协调领域对象、事务、权限校验、外部系统调用和异步任务。

它不直接承载复杂业务规则本身，而是组织领域对象完成业务事件。

---

## 5.1 ProjectService

负责对象：

```
Project
ProjectOrder
ProjectModel
```

核心能力：

```
校验 VDrive 文件夹链接
创建项目
查询项目详情
项目加单
删除项目
项目历史检索
```

典型事件：

```
ValidateVDriveFolderUrl
CreateOrReuseProject
AddProjectOrder
DeleteProject
```

说明：

```
项目删除是软删除。
Project.status = deleted 后，普通列表不再展示，但历史数据保留。
```

---

## 5.2 RuleService

负责对象：

```
BusinessRuleVersion
BusinessCheckRule
AIExecutionRule
RuleSnapshot
```

核心能力：

```
维护业务规则
维护 AI 执行规则
发布业务规则版本
查询已发布规则
生成业务规则快照
生成 AI 执行规则快照
```

规则分层：

```
BusinessCheckRule
  面向业务人员
  用于点检页面展示、报告引用、生成 InspectionItem

AIExecutionRule
  面向系统后台
  用于真实 AI / 系统自动检查执行
```

关键原则：

```
业务规则和 AI 执行规则必须分离。
业务规则字段不能直接等同于 AI 执行规则。
```

---

## 5.3 InspectionService

负责对象：

```
InspectionTask
InspectionRound
InspectionItem
EngineerDecision
RectificationItem
FollowUpItem
```

核心能力：

```
创建点检任务
创建点检轮次
生成检查项实例
确认检查项
归档当前轮
生成整改项
生成待跟进项
触发复查
作废任务
```

典型事件：

```
CreateInspectionTask
ConfirmInspectionItem
ArchiveCurrentRound
MarkRectificationDone
UndoRectificationDone
TriggerRecheck
CloseFollowUpItem
VoidInspectionTask
```

说明：

```
InspectionTask 是点检域主聚合根。
InspectionService 是系统中最核心的应用服务。
```

---

## 5.4 AIExecutionService

负责对象：

```
AICheckResult
AICandidateFile
AIExecutionRuleSnapshot
FileObject
FolderObject
```

核心能力：

```
调度自动检查任务
读取 AI 执行规则快照
定位文件夹
扫描候选文件
选择候选文件
执行文件存在性判断
执行文件内容判断
执行系统直连判断
生成 AI 初判
异常降级转人工
```

典型事件：

```
StartAutoCheck
CompleteAIResult
SelectCandidateFile
ManualFallback
```

说明：

```
AIExecutionService 只生成 AI 初判。
工程师最终确认仍由 InspectionService 处理。
```

---

## 5.5 ReportService

负责对象：

```
InspectionReport
ReportItem
ReportCorrection
```

核心能力：

```
生成或更新节点报告
追加多轮过程记录
计算报告综合结论
更正报告明细
导出 PDF
导出 Excel
查询历史报告
```

典型事件：

```
UpdateReportAfterArchive
CorrectReportItem
ExportReportPdf
ExportReportExcel
```

说明：

```
一个 InspectionTask 只有一份 InspectionReport。
报告不绑定单个轮次。
报告是否更正通过 ReportCorrection 推导，不需要单独存 status。
```

---

## 5.6 UserService

负责对象：

```
User
Permission
```

核心能力：

```
登录
获取当前用户
用户权限查询
用户状态校验
```

---

## 5.7 AdminService

负责对象：

```
User
Permission
SystemSetting
AuditLog
```

核心能力：

```
用户管理
权限管理
系统设置
自动检查开关
审计日志查询
```

---

# 6. Domain Layer：领域模型层

领域模型层保存核心业务概念与业务规则。

核心聚合：

```
Project
BusinessRuleVersion
InspectionTask
InspectionReport
User
```

最核心聚合：

```
InspectionTask
```

InspectionTask 拥有：

```
InspectionRound
InspectionReport
RectificationItem
FollowUpItem
RuleSnapshot
```

InspectionRound 拥有：

```
InspectionItem
```

InspectionItem 关联：

```
AICheckResult
AICandidateFile
EngineerDecision
```

BusinessRuleVersion 拥有：

```
BusinessCheckRule
```

BusinessCheckRule 关联：

```
AIExecutionRule
```

InspectionReport 拥有：

```
ReportItem
ReportCorrection
```

---

# 7. Infrastructure Layer：基础设施层

## 7.1 PostgreSQL

用于存储核心业务数据：

```
用户
权限
项目
业务规则
AI执行规则
规则快照
点检任务
点检轮次
检查项
AI初判结果
候选文件
工程师确认
整改项
待跟进项
报告
报告更正
审计日志
```

---

## 7.2 Redis

用于：

```
Session缓存
任务队列
自动检查进度缓存
短期扫描结果缓存
```

---

## 7.3 Object Storage

用于：

```
下载后的源文件副本
文件解析中间结果
OCR图片切片
报告PDF
导出Excel
```

---

## 7.4 Task Queue

用于异步执行：

```
VDrive文件夹扫描
文件下载
Excel / Word / PPT解析
OCR
LLM调用
系统直连查询
报告导出
```

可选实现：

```
Celery
RQ
Arq
```

---

## 7.5 VDrive Adapter

VDrive 不支持本地路径访问，系统通过 HTTPS 文件夹链接接入。

输入：

```
VDrive 文件夹链接
```

示例：

```
https://docs.XXXX.com/indrive#/index?id=enterprise_922df4e1-d844-4bf7
```

处理流程：

```
解析 folderGuid
  ↓
调用 GetFolderInfoByGuid
  ↓
获得 folderId
  ↓
调用 GetFileAndFolderList
  ↓
递归扫描文件夹和文件
  ↓
转换为 FolderObject / FileObject
```

输出 FolderObject：

```
folder_guid
folder_id
parent_folder_id
folder_name
folder_path
creator_name
created_time
```

输出 FileObject：

```
file_guid
file_id
parent_folder_id
file_name
file_ext
file_size
file_version
creator_name
created_time
modified_time
```

设计原则：

```
业务服务不直接依赖 VDrive 原始接口字段。
所有 VDrive 访问都通过 VDrive Adapter。
```

---

## 7.6 QMS Adapter

负责 PIL 问题查询。

输入：

```
项目机型
QG节点
```

输出：

```
关闭率
未关闭问题数
严重度分布
异常问题明细
```

---

## 7.7 UCM Adapter

负责 QG4 量产 SOP / 工段数据查询。

输入：

```
机型
```

输出：

```
工段字段
是否 FA
来源记录
```

---

## 7.8 LLM Provider / OCR / Parser

用于 AI 执行子系统。

能力：

```
Excel解析
Word解析
PPT解析
OCR识别
Prompt调用
结构化结果生成
```

---

# 8. AI 执行子系统

AI 执行子系统是独立子系统，由 AIExecutionService 协调。

## 8.1 输入

```
InspectionItem
BusinessRuleSnapshot
AIExecutionRuleSnapshot
Project上下文
VDrive folderId
机型列表
```

## 8.2 核心组件

```
FileLocator
CandidateSelector
FileDownloader
FileParser
PromptBuilder
ModelInvoker
ResultBuilder
FallbackHandler
```

---

## 8.3 FileLocator：文件定位器

职责：

```
根据 AIExecutionRuleSnapshot 定位目标文件夹和候选文件。
```

输入：

```
VDrive folderId
target_folder_match
file_match
```

输出：

```
候选文件集合
```

---

## 8.4 CandidateSelector：候选文件选择器

职责：

```
根据 AIExecutionRuleSnapshot 中的选择策略推荐候选文件。
```

典型策略：

```
最新修改时间优先
汇总 / master / summary 优先
文件大小优先
Sheet 数量优先
人工选择
```

输出：

```
推荐候选文件
候选文件排序
推荐原因
```

---

## 8.5 FileParser：文件解析器

职责：

```
根据文件类型解析 Excel / Word / PPT / 图片。
```

输出：

```
结构化文本
表格内容
图片OCR结果
解析异常
```

---

## 8.6 PromptBuilder：Prompt 构造器

职责：

```
根据 BusinessRuleSnapshot 和 AIExecutionRuleSnapshot 构造模型输入。
```

说明：

```
业务规则提供检查目标和业务语义。
AI执行规则提供解析策略、判断标准和输出格式。
```

---

## 8.7 ModelInvoker：模型调用器

职责：

```
调用 LLM 或视觉模型完成复杂内容判断。
```

说明：

```
一期文件存在性判断不一定需要 LLM。
文件内容判断、跨文件一致性判断、图片参数识别可引入 LLM / OCR。
```

---

## 8.8 ResultBuilder：结果构造器

职责：

```
将 AI 输出转换为标准 AICheckResult。
```

输出：

```
ai_status
ai_result
evidence_text
source_system
raw_result_json
candidate_files
```

---

## 8.9 FallbackHandler：降级处理器

职责：

```
处理异常、无候选文件、多候选文件、无法判断等情况。
```

典型降级：

```
多候选文件 → candidate_waiting
未找到文件 → manual_required 或 ai_completed + not_found
解析失败 → manual_required
PPT格式不支持内容检查 → manual_required
外部系统异常 → manual_required
```

---

## 8.10 LangGraph 定位

LangGraph 不是系统主流程引擎。

一期不强制使用 LangGraph。

可在后续复杂 AI 执行链路中用于：

```
跨文件比对
多步骤解析
OCR + LLM 分支
异常重试
人工确认前的复杂推理链路
```

边界：

```
LangGraph 只能存在于 AI 执行子系统内部。
不能控制 InspectionTask、InspectionRound、InspectionReport 的业务状态。
```

---

# 9. 核心业务时序

## 9.1 创建点检任务时序

```
前端提交项目信息 + VDrive文件夹链接 + QG节点
  ↓
ProjectService 校验 VDrive 链接
  ↓
VDriveAdapter 解析 folderGuid 并获取 folderId
  ↓
ProjectService 创建或复用 Project
  ↓
RuleService 获取当前已发布 BusinessRuleVersion
  ↓
RuleService 获取关联 AIExecutionRule
  ↓
RuleService 生成 BusinessRuleSnapshot
  ↓
RuleService 生成 AIExecutionRuleSnapshot
  ↓
InspectionService 创建 InspectionTask
  ↓
InspectionService 创建第 1 轮 InspectionRound
  ↓
InspectionService 根据 BusinessRuleSnapshot 生成 InspectionItem
  ↓
AIExecutionService 根据 AIExecutionRuleSnapshot 投递自动检查任务
  ↓
AuditLog 记录创建任务事件
```

说明：

```
BusinessRuleSnapshot 用于页面展示、报告引用、检查项生成。
AIExecutionRuleSnapshot 用于真实自动检查执行。
```

---

## 9.2 自动检查时序

```
Task Queue 启动自动检查任务
  ↓
AIExecutionService 读取 InspectionItem
  ↓
AIExecutionService 读取 AIExecutionRuleSnapshot
  ↓
VDriveAdapter 扫描文件夹
  ↓
FileLocator 定位目标文件夹和候选文件
  ↓
CandidateSelector 推荐候选文件
  ↓
若为存在性检查，直接形成初判
  ↓
若为内容检查，下载并解析文件
  ↓
必要时调用 OCR / LLM
  ↓
ResultBuilder 生成 AICheckResult
  ↓
写入 AICandidateFile
  ↓
更新 InspectionItem.status
  ↓
前端轮询或 WebSocket 展示检查状态
```

---

## 9.3 工程师确认时序

```
工程师打开检查项详情
  ↓
前端展示 BusinessRuleSnapshot 信息
  ↓
前端展示 AICheckResult 和 CandidateFile
  ↓
工程师确认满足 / 不满足 / 带条件满足 / 不适用
  ↓
InspectionService 校验必填项
  ↓
InspectionService 写入 EngineerDecision
  ↓
InspectionService 更新 InspectionItem.final_result
  ↓
InspectionService 更新 InspectionItem.status = confirmed
  ↓
若全部检查项已确认，归档按钮可用
```

---

## 9.4 归档当前轮时序

```
工程师点击触发归档
  ↓
InspectionService 校验当前轮所有 InspectionItem 已确认
  ↓
InspectionService 汇总 EngineerDecision
  ↓
InspectionService 计算 FULL-GO / C-GO / NO-GO
  ↓
InspectionService 更新 InspectionRound.status = archived
  ↓
ReportService 创建或更新 InspectionReport
  ↓
ReportService 更新 ReportItem.process_records
  ↓
若结果为 NO-GO，InspectionService 生成 RectificationItem
  ↓
若结果为 C-GO，InspectionService 生成 FollowUpItem
  ↓
InspectionService 更新 InspectionTask.status
  ↓
AuditLog 记录归档事件
```

---

## 9.5 整改复查时序

```
InspectionTask.status = rectifying
  ↓
工程师查看 RectificationItem
  ↓
工程师标记整改完成
  ↓
InspectionService 写入 marked_done_by / marked_done_at
  ↓
所有整改项均 marked_done_at 不为空
  ↓
工程师点击触发复查
  ↓
InspectionService 创建下一轮 InspectionRound
  ↓
InspectionService 仅为上一轮 fail 项生成新的 InspectionItem
  ↓
AIExecutionService 投递新轮自动检查任务
  ↓
InspectionTask.status = running
```

---

## 9.6 报告更正时序

```
授权用户在报告页更正单项结论
  ↓
ReportService 校验权限和更正说明
  ↓
ReportService 写入 ReportCorrection
  ↓
ReportService 更新 ReportItem 当前最终结论
  ↓
ReportService 重新计算 InspectionReport 综合结论
  ↓
AuditLog 记录更正事件
```

说明：

```
报告更正不修改 AICheckResult。
报告更正不删除 EngineerDecision。
报告更正不删除 process_records。
```

---

# 10. 状态设计原则

## 10.1 必须入库的状态

这些状态表示业务生命周期或异步执行阶段，必须入库：

```
User.status
Project.status
BusinessRuleVersion.status
InspectionTask.status
InspectionRound.status
InspectionItem.status
AICheckResult.ai_status
FileParseJob.status
```

---

## 10.2 不入库的展示状态

以下状态运行时推导：

```
RectificationItem 展示状态
FollowUpItem 展示状态
InspectionReport 是否更正
```

推导规则：

```
整改项已完成 = marked_done_at 不为空
整改项已超期 = marked_done_at 为空，且 planned_finish_date 已过

待跟进已落实 = closed_at 不为空
待跟进已超期 = closed_at 为空，且 planned_finish_date 已过

报告已更正 = 存在 ReportCorrection
```

---

# 11. 事务边界

## 11.1 创建点检任务

必须在一个事务内完成：

```
创建 Project / ProjectOrder / ProjectModel
创建 InspectionTask
创建 RuleSnapshot
创建 InspectionRound
创建 InspectionItem
写 AuditLog
```

自动检查任务投递可以在事务提交后执行。

---

## 11.2 归档当前轮

必须在一个事务内完成：

```
更新 InspectionRound
更新 InspectionTask
创建或更新 InspectionReport
更新 ReportItem
生成 RectificationItem / FollowUpItem
写 AuditLog
```

---

## 11.3 触发复查

必须在一个事务内完成：

```
校验整改项完成
创建新 InspectionRound
创建新 InspectionItem
更新 InspectionTask
写 AuditLog
```

自动检查任务投递可以在事务提交后执行。

---

## 11.4 报告更正

必须在一个事务内完成：

```
写 ReportCorrection
更新 ReportItem
重新计算 InspectionReport 综合结论
写 AuditLog
```

---

# 12. 审计日志原则

必须记录的业务事件：

```
登录
创建任务
删除项目
启动自动检查
写入 AI 初判
选择候选文件
转人工判断
确认检查项
推翻 AI 初判
归档当前轮
标记整改完成
撤销整改完成
触发复查
关闭待跟进项
更正报告
发布业务规则版本
修改 AI 执行规则
修改用户权限
```

审计日志至少包含：

```
操作人
操作时间
操作对象类型
操作对象ID
操作前数据
操作后数据
IP地址
```

---

# 13. 推荐技术栈

## 13.1 前端

```
React / Next.js
TypeScript
Tailwind CSS
Shadcn UI
TanStack Query
Zustand
```

## 13.2 后端

```
Python
FastAPI
SQLAlchemy
Pydantic
Alembic
```

## 13.3 数据库与任务

```
PostgreSQL
Redis
Celery / RQ / Arq
Object Storage
```

## 13.4 AI 与文件解析

```
openpyxl
python-docx
python-pptx
PyMuPDF
OCR Service
OpenAI Compatible API
LangGraph（后续可选）
```

---

# 14. 一期开发范围建议

## 14.1 一期必做

```
登录与权限
项目创建
VDrive 文件夹链接校验
业务规则配置
AI执行规则后台配置
规则快照
点检任务
点检轮次
检查项实例
文件存在性判断
多候选文件推荐
工程师确认
归档
一任务一报告
整改项
复查
待跟进项
检查档案
审计日志
```

## 14.2 一期可降级

```
QMS / UCM 可先做模拟接口或人工录入
PDF / Excel 导出可先做基础版
文件内容判断先限定 Excel 模板
AI执行规则可先通过后台配置文件维护，不一定做页面
```

## 14.3 暂缓

```
PATS 与 CP 深度一致性核对
CP 与 SOP 深度一致性核对
复杂 OCR
跨文件语义比对
向量知识库
LangGraph 编排
```

---

# 15. 架构结论

CheckFlow 的主流程由 InspectionTask 驱动。

关键架构判断：

```
1. InspectionTask 是点检业务的主聚合根。
2. BusinessRule 与 AIExecutionRule 必须分离。
3. 创建任务时必须同时生成 BusinessRuleSnapshot 与 AIExecutionRuleSnapshot。
4. InspectionItem 是规则生成的实例，不是规则本身。
5. 一个 InspectionTask 只有一份 InspectionReport。
6. 多轮点检记录进入 ReportItem.process_records。
7. AIExecutionService 只产生 AI 初判，不产生最终业务结论。
8. VDrive 通过 Adapter 接入，不使用本地路径。
9. 可推导展示状态不入库。
```

后续数据库、状态机、API、AI执行架构均应以本架构为基准，不再基于早期 v0.2 架构版本继续修补。