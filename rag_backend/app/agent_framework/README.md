# Agent Framework

该目录提供智能家居应用的通用 Agent 基座、LLM 适配器、工具管理和流式调用能力。

领域工具由 `app/home_automation/` 提供，通用知识检索通过稳定的 `search_enterprise_knowledge` 接口接入智能家居知识库。控制请求必须经过设备白名单、状态校验、幂等校验和 MQTT 回执处理。
