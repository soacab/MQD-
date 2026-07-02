# Repository Guidelines

## 项目结构与模块组织

本仓库当前主要保存 CheckFlow / MQD 点检项目的产品与技术设计文档，以及一个静态原型。根目录下的 Markdown 文件分别覆盖业务方案、领域模型、系统架构、数据库设计、状态机、后端 API 与 MVP 开发任务拆分。`CheckFlow_原型.html` 是独立 UI 原型；预览时使用 Microsoft Edge，不要使用 Chrome。

后续进入工程实现时，优先沿用 MVP 文档中的建议结构：

- `backend/app/`：FastAPI 应用、领域服务、仓储、Schema、集成适配器与 API 路由。
- `backend/alembic/`：数据库迁移脚本。
- `backend/tests/`：后端测试。
- `frontend/`：React / Next.js / TypeScript 前端应用、API Client、路由、布局与组件。

## 构建、测试与本地开发命令

当前已包含后端 `pyproject.toml` / `uv.lock`、前端 `frontend/package.json` / `package-lock.json`，以及后端 unittest、前端结构测试和前端构建命令。常用检查命令：

- `rg "关键词" .`：快速检索全部设计文档。
- `open -a "Microsoft Edge" CheckFlow_原型.html`：用 Edge 打开静态原型。
- `.venv/bin/python -m unittest discover -s backend/tests -p "test_*.py" -v`：运行后端默认测试。
- `cd frontend && npm test`：运行前端结构测试。
- `cd frontend && npm run build`：运行前端生产构建。

项目初始化阶段优先使用 Docker Compose 提供 PostgreSQL；前后端默认在本机直接运行，不要求一开始整体容器化。

完整跨笔记本开发流程、本地启动策略和 Docker 化节奏以 `README.md` 为准；不要在本文件重复维护完整教程。

当前前端未配置 ESLint，`npm run lint` 不是可用验收命令。完整启动命令、端口登记和数据库初始化流程以 `README.md` 为准。

## 编码风格与命名约定

文档默认使用中文，除非原文件已经明确使用英文。编辑 Markdown 时保留现有标题层级和表达风格，避免无关格式化。未来代码应遵循既定技术栈：后端使用 Python / FastAPI / SQLAlchemy / Pydantic，前端使用 React / Next.js / TypeScript / Tailwind / Shadcn UI。Python 模块使用 `snake_case`，React 组件使用 `PascalCase`，目录名优先使用小写或 `kebab-case`。

## 测试指南

本仓库已有可执行测试。后端测试放在 `backend/tests/`，文件命名为 `test_*.py`；默认用 `.venv/bin/python -m unittest discover -s backend/tests -p "test_*.py" -v` 运行。前端当前使用 `frontend/tests/frontend-structure.test.mjs`，默认用 `cd frontend && npm test` 运行；生产构建用 `cd frontend && npm run build` 验证。文档变更仍需人工校验链接、标题层级、术语一致性和相关设计文件是否同步。

## 提交与 Pull Request 规范

本仓库已使用 Git/GitHub 管理。提交信息使用简短祈使句，例如 `docs: update local development notes` 或 `feat: scaffold health check`。PR 应说明变更范围、影响的文档或模块、已执行的验证；涉及 UI 或原型变化时附截图。

## 工作方式与 Git 安全规则

按“小步提交”方式工作。每次只完成一个可验证的小任务；复杂任务应按任务文档或已确认计划拆成小步推进。每个小任务完成后先验证，再提交。不要提交失败的中间状态。

验证规则：

- 优先运行和本次改动最相关的测试或检查。
- 如果项目已有默认测试命令，以 `README.md` 或本文件记录的命令为准。
- 当前尚无测试脚本时，文档变更至少运行 `git diff --check`，并人工核对相关 Markdown 内容。
- 当前前端未配置 ESLint，不要把 `npm run lint` 当作默认验收命令。

提交规则：

- 提交前必须查看 `git status` 和 `git diff --stat`。
- 暂存时优先使用明确文件路径，例如 `git add README.md AGENTS.md`。
- 每次 commit 只包含本次小任务相关改动。
- commit message 使用清晰的英文或中文动词开头。
- 不要 `git push`，除非用户明确要求。

允许执行：

```bash
git add <相关文件>
git commit -m "清晰的提交信息"
```

禁止执行，除非用户明确授权：

```bash
git push
git reset --hard
git clean -fd
git rebase
git checkout .
```

完成汇报需包含：完成了哪些小任务、每次提交的 commit hash 和 commit message、每次提交前运行的验证命令，以及是否还有未完成事项或风险。

## 代码协作实践

非琐碎任务开始前，必须先说明当前事实、关键假设、可能歧义、取舍理由、最小改动范围、完成标准和验证方式。明显的一行修复、纯文案小改或等价低风险调整，可按常识简化，但不能跳过必要验证。

编码和调试时遵循以下规则：

- 先读项目再动手；优先查看现有文档、入口、类型、测试、配置和错误全文，不要看到需求或报错类型就直接套用惯用方案。
- 需求存在歧义时，把多种合理理解摊开说明；如果关键边界仍不清楚，先澄清，不要把假设藏进代码。
- 优先选择满足当前目标的最少代码；不新增未被要求的抽象层、扩展点、配置项、兼容框架或依赖。
- 只修改完成当前目标所必需的代码与文档；不顺手重构无关模块、改名、换风格或整理相邻代码。
- 修 bug 先复现或解释为何无法复现，再基于完整错误、数据流和边界条件定位；不要凭报错类型猜修法。
- 如果实现过程中发现方案明显变重、改动范围扩大或需要新增依赖，应暂停说明原因和更小替代方案。

交付前必须证明结果：

- 优先运行与本次改动最相关的测试、构建、静态检查或可复现步骤。
- 没有可执行测试时，文档变更至少运行 `git diff --check`，并人工核对标题层级、链接、术语和相关规则是否一致。
- 汇报时说明实际验证命令、结果、仍未验证的部分、不确定性、关键选择和剩余风险。

常见失败模式需要主动规避：厨房水槽式改动、错误抽象、失控重构、隐藏假设、未读完整错误、未验证就声称完成。

## 任务文档使用规则

`doc/tasks/progress.md` 是开发任务总入口，用于查看模块优先级、依赖顺序和整体进度。执行具体模块前，先读取 `doc/tasks/progress.md`；如对应的 `doc/tasks/<module-name>.md` 仍存在，再读取模块文件中的目标、前置依赖、最小任务清单和验收标准推进。

完成子任务后，优先更新仍存在的对应模块文件 checklist；若模块文件已清理，则直接更新 `doc/tasks/progress.md` 中的状态、缺口和下一步。完成整个模块后，必须更新 `doc/tasks/progress.md`。P2 暂缓模块只有在 P0/P1 验收完成或用户明确要求时才开始。

## Agent 专用说明

默认使用中文沟通。非简单修改按“代码协作实践”执行，先说明假设、边界、成功标准和验证方式，再做最小必要修改。

解决问题、修 BUG、设计架构或方案时，必须从第一性原理出发，先明确事实、约束、目标和可验证标准，再选择实现路径。

完成相对复杂的任务后，开启多 Agent 对抗性审查，重点检查假设、边界条件、架构取舍、潜在回归和验证缺口。
