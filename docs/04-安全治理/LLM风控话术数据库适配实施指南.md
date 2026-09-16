# 智能家居安全规则接入指南

## 1. 接入边界

安全规则分为两层：

1. `app/security`：处理认证、租户、限流、出站访问和通用交互安全；
2. `app/home_automation/safety_rules.py`：处理设备注册、类型、在线、动作、TTL、幂等和 ack。

设备工具和 HTTP API 都必须经过第二层，前端和 Agent 不得绕过后端直接控制设备。

## 2. 运行配置

```text
HOME_DEVICE_ADAPTER=simulated
MQTT_ACK_TIMEOUT_SECONDS=5
```

默认模拟适配器用于本地开发；切换为 `mqtt` 前必须确认 Broker、认证、ACL/TLS 和 ESP32 接线。密码只放在本地环境变量或密钥管理系统中。

## 3. 接入检查

- 设备 ID 来自注册表，不接受用户任意拼接；
- 设备类型和动作来自枚举/白名单；
- 控制参数经过 Pydantic 和安全规则校验；
- 命令带过期时间和 request_id；
- MQTT 发布后等待匹配 ack；
- 所有拒绝、超时和异常都写入审计，但不记录凭据。

## 4. 回归命令

```powershell
cd financial_rag\rag_backend
..\.venv\Scripts\python.exe -m pytest -q `
  tests/unit/test_home_automation_service.py `
  tests/unit/test_home_automation_simulator.py `
  tests/unit/test_home_automation_tools.py `
  tests/unit/test_home_domain_routing.py `
  tests/unit/test_home_orchestrator_routing.py `
  tests/unit/test_home_specialist.py `
  tests/unit/test_interaction_safety.py `
  tests/unit/test_outbound_url_policy.py `
  tests/unit/test_rate_limit_security.py `
  tests/unit/test_rule_repository.py `
  tests/unit/test_session_access.py `
  tests/unit/test_tool_authorization.py
```

完整验证还需执行前端 `npm run build` 和 `git diff --check`。实机联调另按 [MQTT 联调说明](../02-技术方案/MQTT联调说明.md) 记录 Broker、固件和接线版本。
