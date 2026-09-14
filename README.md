# 大模型 + RAG 智能家居知识库

一个面向企业知识问答与智能家居控制的全栈应用。项目以 FastAPI 提供后端 API，以 Vue 3 + Vite 提供管理与对话界面，并使用 LangChain/LangGraph 编排 RAG 检索、工具调用和多智能体流程。

## 项目简介

系统将文档知识库、检索增强生成（RAG）、多轮会话和智能家居设备控制整合在同一套服务中：

- 用户可以上传和管理知识文档，进行检索、问答和多轮对话。
- Agent 可以根据意图选择检索、记忆、工具或专业智能体完成任务。
- 智能家居能力作为独立领域模块接入，支持设备状态查询、环境读取、灯和风扇控制以及预置场景。
- 默认使用模拟设备适配器，便于在没有真实硬件和 MQTT Broker 的情况下开发与测试。

## 主要功能

### RAG 知识库

- 文档上传、解析、切分、索引和检索。
- 基于向量检索的知识问答与上下文增强生成。
- 支持会话、长期记忆、知识图谱和多模态配置等扩展能力。
- 提供知识库、搜索、聊天、反馈和对话日志等 API。

### Agent 与工作流

- 使用 LangGraph 编排 Agent 工作流，支持 ReAct 等 Agent 模式。
- 支持多智能体路由、工具发现、工具调用追踪、Agent Trace 和人工审核。
- 支持流式响应、任务状态、工作流事件、群聊和可观测性接口。
- 可接入项目配置的 LLM、嵌入模型和外部服务；密钥通过环境变量配置。

### 智能家居

智能家居 API 前缀为 `/api/v1/home`，当前提供：

- `GET /devices`：列出已注册设备及在线状态。
- `GET /devices/{device_id}`：查询单个设备。
- `POST /devices/{device_id}/state`：控制设备开关。
- `GET /environment`：读取房间环境传感器数据。
- `POST /scenarios`：执行 `sleep`、`away`、`movie` 等预置场景。

Agent 只能调用固定的家居工具，例如 `get_device_status`、`list_home_devices`、`read_home_environment`、`set_light_state`、`set_fan_state` 和 `run_home_scenario`。控制链路会校验设备注册信息、设备类型、在线状态、命令状态和请求幂等信息。

- `HOME_DEVICE_ADAPTER=simulated`：使用内存模拟设备，默认值。
- `HOME_DEVICE_ADAPTER=mqtt`：通过 MQTT 适配器连接真实设备，使用结构化 JSON、QoS 1、`request_id` 幂等和 ack 回执。
- 硬件原型仅适合低压 LED 和 5V 风扇；不要将原型直接连接到 220V 市电。

### 前端界面

前端提供登录、知识库管理、对话、Agent 追踪、日志、系统配置和智能家居设备页面。前端 API 地址由 `VITE_API_BASE` 控制，未设置时使用相对路径或 Vite 代理。

## 项目结构

```text
.
├── rag_backend/
│   ├── app/
│   │   ├── api/v1/endpoints/       # FastAPI 路由
│   │   ├── home_automation/        # 设备模型、服务、固定工具和适配器
│   │   ├── multi_agent_system/     # Agent、路由和能力配置
│   │   └── prompts/                # Agent 提示词与知识种子
│   ├── tests/                      # 后端测试
│   ├── .env.example                # 后端环境变量模板
│   ├── docker-compose.yml          # PostgreSQL、Redis、Neo4j、MinIO 等服务
│   └── requirements.txt
├── rag_frontend/
│   ├── src/                        # Vue 3 前端源码
│   ├── package.json
│   └── .env.example
├── mcp_server/                     # MCP 相关服务代码
├── 530.sql                         # 数据库初始化/迁移相关脚本
└── README.md
```

## 环境要求

- Python 3.11 及以上。
- Node.js 18 及以上和 npm。
- Docker Desktop（推荐，用于启动 PostgreSQL、Redis、Neo4j、MinIO 等依赖）。
- 一个可用的 LLM/嵌入模型服务及其 API 密钥；具体提供商按 `rag_backend/.env` 配置。

## 安装

### 1. 获取代码

```powershell
git clone https://github.com/ch20050719-hue/-RAG-.git
Set-Location -Path .\-RAG-
```

### 2. 配置后端

```powershell
Set-Location -Path .\rag_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

然后编辑 `rag_backend/.env`，至少配置数据库密码、`SECRET_KEY` 和所使用模型服务的 API 密钥。`.env` 只保存在本地，不要提交到 Git。

### 3. 启动基础服务

在 `rag_backend` 目录执行：

```powershell
docker compose up -d db redis pgbouncer neo4j minio
```

如果希望由 Docker 构建并运行后端，也可以执行 `docker compose up -d`；本地开发时通常只启动基础服务，再单独运行 FastAPI。

### 4. 启动后端

仍在 `rag_backend` 目录执行：

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可打开 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 OpenAPI 文档。

### 5. 启动前端

新开一个终端，在项目根目录执行：

```powershell
Set-Location -Path .\rag_frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

默认访问 [http://localhost:5173](http://localhost:5173)。如后端不在 `http://127.0.0.1:8000`，请修改 `rag_frontend/.env` 中的 `VITE_API_BASE`。

## 智能家居本地运行

不连接硬件时使用默认模拟适配器：

```powershell
Set-Location -Path .\rag_backend
.\.venv\Scripts\Activate.ps1
$env:HOME_DEVICE_ADAPTER = "simulated"
python -m uvicorn app.main:app --reload --port 8000
```

需要 MQTT 联调时，在 `.env` 中设置：

```dotenv
HOME_DEVICE_ADAPTER=mqtt
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=home-backend
MQTT_ACK_TIMEOUT_SECONDS=5
```

MQTT Broker、设备固件、Topic 和接线必须与联调环境保持一致。模型和用户请求不能直接指定 GPIO 或任意 Topic。

## 测试与构建

运行当前智能家居核心单元测试：

```powershell
Set-Location -Path .\rag_backend
python -m pytest tests/unit/test_home_specialist.py tests/unit/test_home_orchestrator_routing.py tests/unit/test_home_domain_routing.py tests/unit/test_home_automation_tools.py tests/unit/test_home_automation_simulator.py tests/unit/test_home_automation_service.py
```

构建前端：

```powershell
Set-Location -Path .\rag_frontend
npm run build
```

提交前建议在仓库根目录执行：

```powershell
git diff --check
```

## 安全与使用边界

- 不要把 API 密钥、数据库密码、MQTT 凭据或生产配置提交到仓库。
- 生产环境应替换默认密钥，配置 HTTPS、认证、数据库备份和最小权限。
- 智能家居控制必须经过项目提供的固定工具和安全校验。
- MQTT 联调前先确认 Broker、固件版本和设备接线；原型只使用低压 LED 与 5V 风扇。

## 当前合并状态

本仓库的智能家居改造通过独立分支提交，并已生成可供 `master` 审核的合并分支。合并检查结果和风险说明以代码托管平台上的 Pull Request 为准。
