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

每次完成一段可说明的修改后提交并推送：

```bash
git status
git add .
git commit -m "说明这次改了什么"
git push
```

不要把 `.env`、密钥、数据库密码或本地数据库数据提交到 GitHub。需要共享配置格式时，提交 `.env.example`。

## 当前本地开发策略

项目初始化阶段采用轻量 Docker 策略：

- 前端代码默认在本机直接运行。
- 后端代码默认在本机直接运行。
- PostgreSQL 使用 Docker Compose 在本机启动。
- 数据库结构通过 Alembic 迁移管理。
- 初始测试数据通过 seed 脚本生成。

这意味着 GitHub 负责同步代码、迁移脚本和种子数据；Docker 负责提供一致的 PostgreSQL 运行环境。数据库真实数据不通过 GitHub 同步。需要在另一台电脑恢复开发环境时，优先通过迁移和 seed 脚本重建。

## 本地启动命令

当前尚未完成工程脚手架，以下命令会在 `00 项目初始化` 实现后补齐。

### 启动 PostgreSQL

```bash
docker compose up -d
```

### 启动后端

```bash
# 待补充：FastAPI 本地启动命令
```

### 启动前端

```bash
# 待补充：Next.js 本地启动命令
```

### 数据库迁移

```bash
# 待补充：Alembic 迁移命令
```

### 种子数据

```bash
# 待补充：seed 脚本命令
```

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
