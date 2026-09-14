# 智能家居多智能体系统

保留 RAG 检索、Agent 调度、多轮会话、黑板任务协作和结果合成接口，当前唯一业务域为智能家居。

- `orchestrator.py`：统一协调家居总管家、环境感知、设备控制和舒适度专家。
- `agents/intent_router_agent.py`：识别设备控制、环境读取、设备状态和家居场景意图。
- `rag_retriever.py`：租户隔离的设备手册、传感器指南、场景定义和安全规则检索。
- `app/home_automation/`：设备服务、安全规则、模拟设备和 MQTT 适配器。

控制类请求必须通过注册工具，不允许 Agent 直接输出 GPIO 或任意 MQTT Topic。
