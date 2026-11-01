# 项目功能说明

> 状态：历史软件方案，仅供回溯。当前项目只维护 STM32 固件与已确认硬件；以根目录 `agents.md`、`readme.md` 和 `docs/02-技术方案/智能家居项目交接说明.md` 为准。本文涉及的旧 Python/RAG/Agent/后端/网页代码已归档至 `F:\agrnt`。

> 项目名称：基于大模型的单房间智能家居环境感知与安全控制系统
> 当前定位：大模型负责自然语言理解、意图提取和固定工具调用；设备状态验证、安全规则和执行回执由后端确定性控制
> 业务范围：仅智能家居；旧财税链路不再作为产品能力维护

## 1. 项目概述

系统采用前后端分离架构，以现有 Agent 编排、多轮会话和设备服务能力为基座，面向 STM32F103C8T6 版本三单房间原型实现环境感知、固定工具控制和安全回执。用户可以通过聊天、机智云 APP 或设备控制台查询设备状态、读取环境数据、控制低压 LED、风扇和喷淋水泵，并调整模式和阈值。

一次典型请求经过以下链路：

```text
用户输入
  → 会话上下文恢复
  → 智能家居意图识别
  → 结构化控制意图与参数
  → 主 Agent 调度环境监测和设备控制子 Agent
  → 调用固定设备工具
  → 安全规则校验
  → 模拟适配器或机智云/受控协议适配器执行
  → ESP8266-01S → STM32F103C8T6
  → 状态/ack 回执
  → 多轮会话中生成可追溯结果
```

## 2. 保留能力与领域边界

保留并继续稳定支持：

- Agent 调度、固定工具调用、流式输出和异步任务；
- 多轮会话、上下文管理、会话权限和租户隔离；
- 认证、审计、限流、出站访问边界和安全监控。

智能家居是唯一业务领域：

- 意图包括设备查询、温湿度/烟雾/火焰/有人状态读取、LED/风扇/水泵/蜂鸣器控制、门锁开关、手动/自动模式切换和阈值调节；
- 设备说明、环境监测、手动/自动规则、场景预设和控制安全规则作为固定配置或提示词素材；
- Agent 不接收 GPIO、任意 Topic 或任意设备命令，只能使用固定工具；
- 正常、睡眠、离家是场景预设；不同场景的人工工具白名单由后端策略强制执行，自动安全联动和环境查询始终保留；
- 旧财税、税务、法务的代码入口、知识种子、提示词和前端入口不再维护。

## 3. 功能模块

### 3.1 设备工具

`app/home_automation/device_tools.py` 是设备操作的唯一工具入口，提供：

> 下列版本三工具是目标能力；当前代码中尚未存在的工具必须先实现并测试后，才能作为已完成能力对外宣称。

- `list_home_devices`：列出已注册设备及在线状态；
- `get_device_status`：读取单个设备状态；
- `read_home_environment`：读取房间温度、湿度、烟雾、火焰和有人状态；
- `set_light_state` / `set_fan_state` / `set_sprinkler_pump_state` / `set_alarm_buzzer_state`：通过固定接口控制 LED、风扇、喷淋水泵和蜂鸣器；
- `open_door` / `close_door`：在门锁状态和设备在线校验通过后，驱动舵机自动开门/关门；普通开门、关门不设置独立服务端确认状态；
- `set_automation_mode` / `set_environment_threshold`：切换手动/自动模式和调整合法阈值。

当前代码约定：`manual` / `automatic` 是设备主控制模式；自动规则只联动风扇、蜂鸣器、水泵和 LED，手动模式由按键或 APP 直接控制设备。

### 3.2 安全规则

控制指令必须依次通过设备注册、设备类型、在线状态、动作白名单、参数范围、命令状态和过期时间校验。每条控制请求带 `request_id`，重复请求返回已有结果，不重复驱动设备。失败时只返回可解释的阻断原因，不泄露底层 Topic 或 GPIO。

### 3.3 MQTT 通信

后端支持 `simulated` 和受控协议适配两种运行方式，使用同一套设备服务与回执模型。机智云数据点不直接暴露给 Agent，需由适配器映射为内部命令；内部协议采用结构化 JSON、命令过期时间和回执，设备通过 telemetry 和状态结果上报数据。

### 3.4 STM32 桌面原型

当前真实硬件目标为 STM32F103C8T6 版本三。STM32 通过 ESP8266-01S 接入机智云，连接 OLED、温湿度、烟雾、火焰、人体传感器、蜂鸣器、低压 LED、5V 风扇、喷淋水泵和舵机门锁。原型禁止接入 220V 市电，执行器需要独立供电并按电路方案共地，固件不接受任意 GPIO 指令。旧 `esp32/esp32_home_node` 仅作为协议参考。

## 4. 代码入口

| 路径 | 职责 |
|---|---|
| `financial_rag/rag_backend/app/home_automation` | 设备模型、服务、安全、模拟与 MQTT 适配器 |
| `financial_rag/rag_backend/app/api/v1/endpoints/home_devices.py` | `/api/v1/home` 设备 API |
| `financial_rag/rag_backend/app/agent_framework` | Agent 执行、工具管理和多轮循环 |
| `financial_rag/rag_backend/app/langgraph` | Agent 工作流编排 |
| `financial_rag/rag_backend/app/services` | 会话和基础服务 |
| `financial_rag/rag_frontend/src/views/HomeDevicesView.vue` | 智能家居控制台 |
| `financial_rag/rag_frontend/src/api/home.ts` | 前端设备 API 客户端 |
| `esp32/esp32_home_node/esp32_home_node.ino` | 历史 ESP32 协议参考；当前正式通信模块为 ESP8266-01S |

## 5. API 与配置

API 前缀为 `/api/v1/home`，接口如下：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/devices` | 查询设备列表 |
| GET | `/devices/{device_id}` | 查询单个设备 |
| POST | `/devices/{device_id}/state` | 下发 `on/off` 控制 |
| POST | `/pump/state` | 控制模拟喷淋水泵 |
| POST | `/buzzer/state` | 控制报警蜂鸣器 |
| POST | `/door/open` | 设备状态允许且在线时驱动舵机自动开门 |
| POST | `/door/close` | 设备状态允许且在线时驱动舵机自动关门 |
| GET | `/environment?room=study` | 查询房间环境 |
| GET/POST | `/automation-mode` | 查询或切换手动/自动主控制模式 |
| GET/POST | `/thresholds` | 查询或调整温度、湿度、烟雾阈值 |
| GET/POST | `/scenarios` | 查询或执行 `normal`、`sleep`、`away` 场景预设 |

默认配置：

```text
HOME_DOMAIN_MODE=1
HOME_DEVICE_ADAPTER=simulated
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_ACK_TIMEOUT_SECONDS=5
```

## 6. 验证状态

- `tests/unit/test_home_*.py`：83 passed；
- `python -m compileall -q app`：通过；
- 前端 `npm run build`：通过；
- 本次修改涉及的代码文件 `git diff --check`：通过；全仓检查仍受既有无关前端文件尾随空格影响；
- 当前环境完整启动还需补齐 `minio` 依赖，硬件 MQTT 联调需另行记录 Broker、固件和接线版本。
