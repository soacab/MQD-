# 04 VDrive 链接校验

## 目标
支持项目创建和任务创建前校验 VDrive 文件夹链接，并保存可用于后续扫描的文件夹标识。

## 参考文档
- `CheckFlow 后端 API 设计 v0 1.md .md`：VDrive API。
- `CheckFlow 系统架构设计 v1.md`：VDrive Adapter。
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 2。

## 前置依赖
- [x] 03 项目管理完成。

## 当前状态复核

当前状态为 🟡 后端链接校验、项目保存链路、任务创建前校验动作和 mock Adapter 边界已具备；真实 VDrive 可访问性校验仍需等真实 Adapter 确认后补齐。总状态以 `doc/tasks/progress.md` 为准，本文件用于记录本模块的具体完成项和待补缺口。

已具备最小实现：

- 后端已支持 VDrive URL 解析、`POST /api/v1/vdrive/validate-folder-link`、项目创建时保存 `vdrive_folder_guid` / `vdrive_folder_id` / `vdrive_folder_name` / `vdrive_folder_path`。
- 后端已支持 `POST /api/v1/projects/{project_id}/vdrive-link` 更新项目 VDrive 链接。
- 创建点检任务时已校验项目状态和项目是否存在 VDrive folderGuid / folderId，缺失时阻断创建；前端新建点检任务表单也已加入项目 VDrive 路径校验动作。
- 项目创建页已有 VDrive 链接校验按钮和校验结果展示。
- VDrive mock 逻辑已抽到 `backend/app/vdrive.py`，后续可替换为真实 Adapter。

待补缺口：

- 当前仍是 mock URL 解析和模拟可访问返回，不代表真实 VDrive 路径可访问。

## 最小任务清单
- [x] T01：实现 VDrive URL 解析器；验收：可从输入链接提取 `folderGuid`。
- [x] T02：实现 `POST /api/v1/vdrive/validate-folder-link`；验收：返回 folderId、folderName、folderPath 或明确错误。
- [x] T03：实现 VDrive Adapter mock；当前 mock 可支撑主流程，并已抽出清晰 Adapter 边界。
- [x] T04：实现项目 VDrive 链接更新接口；验收：项目保存 `vdrive_folder_guid` 和 `vdrive_folder_id`。
- [x] T05：在新建任务表单加入校验路径动作；验收：项目未保存 VDrive 链接或校验未通过时阻断创建动作。
- [x] T06：记录 VDrive 校验失败原因；验收：前端能展示明确错误提示。

## 验收标准
- [x] 可校验 VDrive 文件夹链接。
- [x] 可保存项目 VDrive 标识。
- [x] 路径不可访问时不能创建任务；当前后端有提交时兜底阻断，前端任务创建前已有校验动作。
- [x] mock 与真实 Adapter 之间有清晰替换边界。

## 注意事项
本模块只做链接校验和预览，不执行文件夹扫描。
