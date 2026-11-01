# RAG 智能家居控制平台

本仓库当前只维护智能家居业务，是一个面向个人知识问答与智能家居控制的全栈应用。RAG 检索、Agent 调度和多轮会话是保留的通用基座；设备工具、安全规则、受控协议桥和 STM32F103C8T6 版本三硬件方案是当前业务扩展，旧 ESP32 仅作历史参考。项目以 FastAPI 提供后端 API，以 Vue 3 + Vite 提供管理与对话界面，并使用 LangChain/LangGraph 编排 RAG 检索、工具调用和多智能体流程。

## 项目简介

项目采用 FastAPI + Vue 3 前后端分离架构，将知识检索、对话 Agent 与受控的智能家居设备控制连接起来。系统默认使用模拟设备，便于在没有真实硬件或 MQTT Broker 的情况下开发、测试和演示。

## 主要功能

### RAG 与 Agent 基座

- 文档解析、切分、向量检索和上下文增强问答。
- 多轮会话、流式响应、记忆和来源追踪。
- LangGraph Agent 编排、意图路由、固定工具调用和多智能体协作。
- 认证、租户隔离、限流、审计、人工审核和工具调用追踪。

### 智能家居能力

- 查询已注册设备、在线状态和房间环境数据。
- 控制桌面灯 `desk_light` 与风扇 `desk_fan` 的 `on/off` 状态。
- 执行 `sleep`、`away`、`movie` 预置场景。
- 控制链路校验设备注册、设备类型、在线状态、动作白名单、命令状态和 TTL。
- 默认使用 `simulated` 模拟适配器；联调时可切换到 `mqtt`。

设备控制只能通过 `rag_backend/app/home_automation/device_tools.py` 暴露的固定工具完成，模型、前端和固件不能指定任意 GPIO 或 MQTT Topic。

## 架构

```text
Vue 控制台 / 对话入口
          │ HTTP / SSE
          ▼
FastAPI API
   ├── RAG 检索、来源引用、会话与多轮上下文
   ├── Agent 编排、意图识别和固定工具路由
   └── /api/v1/home 设备查询、控制和场景
                    │
                    ▼
          DeviceService → SafetyRules
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   SimulatedAdapter      受控协议桥 → STM32F103C8T6
```

## 智能家居 API

服务路由前缀为 `/api/v1/home`，请求需要通过项目已有认证依赖：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/devices` | 返回设备列表和状态 |
| GET | `/devices/{device_id}` | 返回单个设备状态 |
| POST | `/devices/{device_id}/state` | `{"state":"on\|off","request_id":"optional"}` |
| GET | `/environment?room=study` | 返回环境传感器快照 |
| POST | `/scenarios` | `{"scenario":"sleep\|away\|movie"}` |

MQTT 控制使用结构化 JSON、QoS 1、`request_id` 幂等和 ack 回执。

## 项目结构

```text
.
├── rag_backend/                 FastAPI、RAG、Agent、会话和设备服务
│   ├── app/home_automation/     设备模型、服务、安全、模拟/MQTT 适配器
│   ├── app/api/v1/endpoints/    HTTP API，含 /api/v1/home
│   └── tests/                   后端测试
├── rag_frontend/                Vue 3 + TypeScript 控制台
├── esp32/esp32_home_node/       旧 ESP32 原型（历史参考）
├── docs/                        智能家居方案、联调和安全文档
├── mcp_server/                  MCP 相关服务代码
└── 530.sql                      数据库初始化/迁移相关脚本
```

## 环境要求

- Python 3.11 及以上。
- Node.js 18 及以上和 npm。
- Docker Desktop（推荐，用于 PostgreSQL、Redis、Neo4j、MinIO 等依赖）。
- 一个可用的 LLM/Embedding 服务及其 API 密钥。

## 安装与启动

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

编辑 `rag_backend/.env`，配置数据库、`SECRET_KEY` 和模型服务密钥。`.env` 只保存在本地，禁止提交真实凭据。

### 3. 启动基础服务

仍在 `rag_backend` 目录执行：

```powershell
docker compose up -d db redis pgbouncer neo4j minio
```

### 4. 启动后端

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)。

### 5. 启动前端

新开终端：

```powershell
Set-Location -Path .\rag_frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

默认访问 [http://localhost:5173](http://localhost:5173)。如后端地址不同，修改 `rag_frontend/.env` 中的 `VITE_API_BASE`。

## 智能家居运行模式

### 模拟模式

模拟模式不需要硬件和 MQTT Broker，是默认配置：

```powershell
Set-Location -Path .\rag_backend
$env:HOME_DEVICE_ADAPTER = "simulated"
python -m uvicorn app.main:app --reload --port 8000
```

### MQTT 联调模式

在 `rag_backend/.env` 中设置：

```dotenv
HOME_DOMAIN_MODE=1
HOME_DEVICE_ADAPTER=mqtt
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=home-backend
MQTT_ACK_TIMEOUT_SECONDS=5
```

Broker、设备固件、Topic 和接线版本必须与联调环境一致。详细说明见 [`docs/02-技术方案/MQTT联调说明.md`](docs/02-技术方案/MQTT联调说明.md)。

## 硬件版本三与历史 ESP32 原型

当前硬件规格以 [`docs/02-技术方案/智能家电版本三功能与硬件规格.md`](docs/02-技术方案/智能家电版本三功能与硬件规格.md) 为准，主控为 STM32F103C8T6，控制低压灯、5V 风扇、28BYJ 窗户和舵机锁门装置。

- 自动模式由本地状态机执行温度、湿度、光照和烟雾阈值联动；云端 Agent 只能通过固定工具提交合法动作和阈值。
- STM32 通过 ESP8266-01S 或受控协议桥与云端通信，不接收任意 GPIO、寄存器或 MQTT Topic。
- USB 灯、USB 风扇、窗户电机和舵机均使用低压独立供电，禁止接入 220V 市电。

旧 ESP32 固件仍保留在 [`esp32/esp32_home_node/`](esp32/esp32_home_node/)，仅用于历史桌面原型参考，不代表当前硬件版本。

## 测试与构建

在 `rag_backend` 目录运行智能家居核心单元测试：

```powershell
python -m pytest tests/unit/test_home_specialist.py tests/unit/test_home_orchestrator_routing.py tests/unit/test_home_domain_routing.py tests/unit/test_home_automation_tools.py tests/unit/test_home_automation_simulator.py tests/unit/test_home_automation_service.py
```

构建前端：

```powershell
Set-Location -Path ..\rag_frontend
npm run build
```

提交前检查：

```powershell
git diff --check
```

最近一次验证：智能家居与安全回归测试 118 passed，前端 Vite 构建通过。

## 安全边界

- 生产环境必须替换默认密钥并使用环境变量或密钥管理服务。
- 不向模型暴露 GPIO、任意 Topic 或未经注册的设备。
- 所有设备控制必须经过固定工具和安全校验。
- STM32 版本三只用于低压 LED、5V 风扇、窗户电机和舵机锁门装置演示，禁止接入 220V 市电。

## 相关文档

- [`docs/README.md`](docs/README.md)：文档导航。
- [`docs/02-技术方案/智能家居改造实施方案.md`](docs/02-技术方案/智能家居改造实施方案.md)：整体实施方案。
- [`docs/02-技术方案/智能家居模拟设备闭环.md`](docs/02-技术方案/智能家居模拟设备闭环.md)：无硬件开发与测试闭环。
- [`docs/02-技术方案/智能家电版本三功能与硬件规格.md`](docs/02-技术方案/智能家电版本三功能与硬件规格.md)：当前 STM32F103C8T6 硬件规格。
