# 04 VDrive 链接校验

## 目标
支持项目创建和任务创建前校验 VDrive 文件夹链接，并保存可用于后续扫描的文件夹标识。

## 参考文档
- `CheckFlow 后端 API 设计 v0 1.md .md`：VDrive API。
- `CheckFlow 系统架构设计 v1.md`：VDrive Adapter。
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 2。

## 前置依赖
- [x] 03 项目管理完成。

## 最小任务清单
- [x] T01：实现 VDrive URL 解析器；验收：可从输入链接提取 `folderGuid`。
- [x] T02：实现 `POST /api/v1/vdrive/validate-folder-link`；验收：返回 folderId、folderName、folderPath 或明确错误。
- [x] T03：实现 VDrive Adapter mock；验收：未接真实 VDrive 时主流程仍可跑通。
- [x] T04：实现项目 VDrive 链接更新接口；验收：项目保存 `vdrive_folder_guid` 和 `vdrive_folder_id`。
- [x] T05：在新建任务表单加入校验路径动作；验收：路径不可访问时阻断下一步。
- [x] T06：记录 VDrive 校验失败原因；验收：前端能展示明确错误提示。

## 验收标准
- [x] 可校验 VDrive 文件夹链接。
- [x] 可保存项目 VDrive 标识。
- [x] 路径不可访问时不能创建任务。
- [x] mock 与真实 Adapter 之间有清晰替换边界。

## 注意事项
本模块只做链接校验和预览，不执行文件夹扫描。
