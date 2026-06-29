# 00 项目初始化

## 目标
搭建 CheckFlow 前后端基础工程，使本地能启动、后端能响应健康检查、前端能访问后端。

## 参考文档
- `CheckFlow MVP 开发任务拆分 v1 0 38e75a5befd780778d1ef8bdd4cd1e65.md`：Phase 0。
- `CheckFlow 系统架构设计 v1.md`：推荐技术栈与分层架构。
- `AGENTS.md`：仓库约定。

## 前置依赖
无。

## 当前复核结论
Phase 0 按 `/health`、本地配置、在线迁移、前端构建和测试入口口径已验证可用。

严格按原 Phase 0 文档仍有偏差：当前 MVP 已明确采用轻量 SQL helper 而非 SQLAlchemy Base / ORM；组件库选型/接入尚未明确。

当前实现已越过纯工程骨架阶段，P0 业务接口集中在 `backend/app/main.py`。后续扩展前应控制该文件继续膨胀，并把业务拆分放到后续重构任务中处理。

## 最小任务清单
- [x] T01：创建 `backend/app/` FastAPI 项目骨架；验收：`app/main.py` 暴露 FastAPI 实例。
- [x] T02：创建 `backend/app/core/` 配置、数据库、异常、日志、CORS 基础模块；验收：模块可被 `main.py` 正常导入。
- [x] T03：创建 `/health` 健康检查接口；验收：本地启动后返回成功状态。
- [x] T04：初始化 Alembic 目录；验收：在线迁移和 offline SQL 生成已验证。
- [x] T05：创建 `frontend/` React / Next.js / TypeScript 项目；验收：前端开发服务器可启动。
- [x] T06：配置前端基础布局、路由和 API Client；验收：API Client 与健康检查已接入，组件库接入未完成/未明确。
- [x] T07：配置 Docker Compose PostgreSQL；验收：贡献者可按文档启动 PostgreSQL，并配置后端数据库连接。
- [x] T08：补充本地启动与测试命令到项目文档；验收：贡献者可按文档启动前后端。

## 验收标准
- [x] 后端 `/health` 可访问。
- [x] 数据库配置入口存在但不要求业务表完成。
- [x] PostgreSQL 可通过 Docker Compose 启动，后端可读取对应数据库连接配置。
- [x] 前端可启动并调用后端健康检查。
- [x] 基础目录已建立，但 `models/schemas/services/repositories/api/v1` 等分层尚未真正沉淀。

## 后续修正项
- 明确是否接入组件库，以及接入到什么程度。
- 后续重构时拆分 `backend/app/main.py` 中的业务路由、服务和数据访问逻辑。

## 注意事项
原计划中本模块只建立可运行骨架，不承载业务接口；当前代码已超出该边界。后续不要继续在项目初始化任务下追加业务实现。
项目初始化阶段只要求 Docker Compose 管理 PostgreSQL，不要求容器化后端或前端。
