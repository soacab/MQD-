# CheckFlow / MQD 点检项目

本仓库用于保存 CheckFlow / MQD 点检项目的设计文档、任务拆分和后续工程实现代码。当前阶段以 MVP 开发落地为目标，优先按 `doc/tasks/progress.md` 中的 P0/P1 顺序推进。

## 跨笔记本开发流程

第一次在新电脑上开发：

```bash
git clone https://github.com/soacab/MQD-.git
cd MQD-
```

每次开始开发前先同步最新代码：

```bash
git pull
```

每次完成一段可说明的修改后提交。只暂存本次小任务相关文件；不要默认推送，除非明确需要同步远端：

```bash
git status
git add <相关文件>
git commit -m "说明这次改了什么"
```

不要把 `.env`、密钥、数据库密码或本地数据库数据提交到 GitHub。需要共享配置格式时，提交 `.env.example`。

## 当前本地开发策略

项目初始化阶段采用轻量 Docker 策略：

- 前端代码默认在本机直接运行。
- 后端代码默认在本机直接运行。
- 后端默认使用 SQLite 便于快速启动和测试；需要按目标环境验证数据库服务时，PostgreSQL 使用 Docker Compose 在本机启动，并通过 `CHECKFLOW_DATABASE_URL` 切换。
- 数据库结构通过 Alembic 迁移管理。
- 初始测试数据通过 seed 脚本生成。

这意味着 GitHub 负责同步代码、迁移脚本和种子数据；Docker 负责提供一致的 PostgreSQL 运行环境。数据库真实数据不通过 GitHub 同步。需要在另一台电脑恢复开发环境时，优先通过迁移和 seed 脚本重建。

## 本地启动命令

### 启动 PostgreSQL

```bash
docker compose up -d
```

使用 PostgreSQL 运行后端时，把数据库连接配置为：

```bash
export CHECKFLOW_DATABASE_URL=postgresql://checkflow:checkflow@127.0.0.1:5432/checkflow
```

不设置时，代码默认使用 `sqlite:///./backend/checkflow.db`，适合本地快速验证。需要自定义配置时，复制 `.env.example` 为 `.env` 后再按本机环境修改；不要提交 `.env`。

### 安装依赖

```bash
uv sync
cd frontend
npm install
cd ..
```

### 启动本地开发服务

```bash
./scripts/dev_up.sh
./scripts/dev_status.sh
```

脚本会通过 `nohup` 后台启动后端和前端，端口、PID 与日志写入 `.dev/`。停止服务：

```bash
./scripts/dev_down.sh
```

不要手动使用 `8000` 作为 CheckFlow 后端端口；该端口可能被其他本地项目占用。后端和前端端口必须以 `codex-port` 登记结果为准，前端必须通过 `NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:${API_PORT}"` 指向登记后的后端端口。

### 手动启动后端

```bash
PORT=$(codex-port reserve "$PWD/backend" api)
uv run uvicorn app.main:app --app-dir backend --reload --reload-dir backend --port "$PORT"
```

### 手动启动前端

```bash
API_PORT=$(codex-port reserve "$PWD/backend" api)
WEB_PORT=$(codex-port reserve "$PWD" dev)
cd frontend
NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:${API_PORT}" npm run dev -- -p "$WEB_PORT"
```

### 数据库迁移

```bash
uv run alembic upgrade head
```

### 种子数据

```bash
uv run alembic upgrade head
PYTHONPATH=backend uv run python -c "from app.seed import seed_database; seed_database()"
```

### 测试

```bash
.venv/bin/python -m unittest discover -s backend/tests -p "test_*.py" -v
cd frontend
npm test
npm run test:e2e
npm run build
```

当前默认后端验收使用项目 `.venv` 中的 `unittest`。`uv run pytest` 暂不作为默认测试入口；在修正本机 Python / pytest 环境和依赖配置前，它可能不会加载项目 `.venv` 中的 FastAPI 依赖。
当前前端未配置 ESLint，`npm run lint` 不是可用验收命令。
前端 E2E 测试使用 Playwright 驱动 Microsoft Edge，并在测试内 mock API 响应；运行 `npm run test:e2e` 前不需要单独启动真实后端。

## Docker 化节奏

一开始只用 Docker Compose 管理 PostgreSQL，不要求容器化前后端。

后续在以下场景再推进整体 Docker 化：

- 需要部署到服务器或演示环境。
- 希望一条命令启动完整系统。
- 多人协作时本机 Python / Node 环境差异开始影响开发。
- 引入 Redis、Celery / RQ / Arq、后台 worker 或更复杂的 VDrive 自动检查任务。

整体 Docker 化时，再补充后端、前端、worker、Redis 等服务的 Dockerfile 和 Compose 配置。

## 任务文档入口

- `doc/tasks/progress.md`：MVP 任务总进度和优先级。
- `doc/tasks/00-project-bootstrap.md`：项目初始化和本地启动基础。
- `doc/tasks/01-database-orm.md`：数据库迁移、ORM 模型和核心约束。
