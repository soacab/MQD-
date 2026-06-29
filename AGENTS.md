# Repository Guidelines

## 项目结构与模块组织

本仓库当前主要保存 CheckFlow / MQD 点检项目的产品与技术设计文档，以及一个静态原型。根目录下的 Markdown 文件分别覆盖业务方案、领域模型、系统架构、数据库设计、状态机、后端 API 与 MVP 开发任务拆分。`CheckFlow_原型.html` 是独立 UI 原型；预览时使用 Microsoft Edge，不要使用 Chrome。

后续进入工程实现时，优先沿用 MVP 文档中的建议结构：

- `backend/app/`：FastAPI 应用、领域服务、仓储、Schema、集成适配器与 API 路由。
- `backend/alembic/`：数据库迁移脚本。
- `backend/tests/`：后端测试。
- `frontend/`：React / Next.js / TypeScript 前端应用、API Client、路由、布局与组件。

## 构建、测试与本地开发命令

当前尚未包含包管理器、构建脚本或测试运行器。可使用以下安全检查命令：

- `rg "关键词" .`：快速检索全部设计文档。
- `open -a "Microsoft Edge" CheckFlow_原型.html`：用 Edge 打开静态原型。

代码脚手架加入后，应在本节补充真实命令，例如 `uv run pytest`、`npm test`、`npm run lint`，以及前后端本地启动命令。

## 编码风格与命名约定

文档默认使用中文，除非原文件已经明确使用英文。编辑 Markdown 时保留现有标题层级和表达风格，避免无关格式化。未来代码应遵循既定技术栈：后端使用 Python / FastAPI / SQLAlchemy / Pydantic，前端使用 React / Next.js / TypeScript / Tailwind / Shadcn UI。Python 模块使用 `snake_case`，React 组件使用 `PascalCase`，目录名优先使用小写或 `kebab-case`。

## 测试指南

本仓库目前没有可执行测试。文档变更应人工校验链接、标题层级、术语一致性和相关设计文件是否同步。后端实现后，测试放在 `backend/tests/`，文件命名为 `test_*.py`。前端实现后，在组件旁或专用测试目录添加组件/流程测试，并把运行命令记录到本文件。

## 提交与 Pull Request 规范

当前目录尚未初始化为 Git 仓库，因此没有可参考的历史提交规范。启用 Git 后，使用简短祈使句提交信息，例如 `docs: add API validation notes` 或 `feat: scaffold health check`。PR 应说明变更范围、影响的文档或模块、已执行的验证；涉及 UI 或原型变化时附截图。

## 任务文档使用规则

`doc/tasks/progress.md` 是开发任务总入口，用于查看模块优先级、依赖顺序和整体进度。执行具体模块前，先读取对应的 `doc/tasks/<module-name>.md`，按其中的目标、前置依赖、最小任务清单和验收标准推进。

完成子任务后，更新对应模块文件中的 checklist；完成整个模块后，再更新 `doc/tasks/progress.md`。P2 暂缓模块只有在 P0/P1 验收完成或用户明确要求时才开始。

## Agent 专用说明

默认使用中文沟通。非简单修改前先说明假设与成功标准。只做与任务直接相关的外科式修改，不重构无关内容。完成后使用最小相关命令验证结果。

解决问题、修 BUG、设计架构或方案时，必须从第一性原理出发，先明确事实、约束、目标和可验证标准，再选择实现路径。

完成相对复杂的任务后，开启多 Agent 对抗性审查，重点检查假设、边界条件、架构取舍、潜在回归和验证缺口。
