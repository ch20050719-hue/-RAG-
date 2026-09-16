# MQTT 联调说明

本文档描述智能家居后端、MQTT Broker 和 ESP32 桌面节点的联调契约。默认开发模式为模拟适配器；只有准备好 Broker 和低压硬件后才切换 MQTT。

## 1. 启动 Broker

演示环境可使用 Mosquitto：

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/config:/mosquitto/config
```

本地配置示例：

```conf
listener 1883
allow_anonymous true
```

匿名配置只适合隔离的本地演示。生产环境必须启用账号、ACL、TLS 和最小权限 Topic 授权。

## 2. 后端配置

在 `rag_backend/.env` 中设置：

```text
HOME_DOMAIN_MODE=1
HOME_DEVICE_ADAPTER=mqtt
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=home-backend
MQTT_ACK_TIMEOUT_SECONDS=5
```

后端仍通过 `DeviceService` 和固定设备工具控制设备，不允许前端、Agent 直接发布 MQTT 消息。

## 3. Topic 契约

```text
home/v1/{room}/{device_id}/state/set     后端 → 设备：控制命令
home/v1/{room}/{device_id}/state/ack     设备 → 后端：执行回执
home/v1/{room}/{device_id}/telemetry     设备 → 后端：传感器/状态数据
home/v1/{room}/{device_id}/availability  设备 → 后端：online/offline
```

当前桌面节点使用：

```text
home/v1/study/desk_light/state/set
home/v1/study/desk_fan/state/set
```

## 4. 消息格式

控制命令：

```json
{
  "request_id": "uuid",
  "action": "set_state",
  "state": "on",
  "expires_at": "2026-09-16T12:00:00+00:00"
}
```

回执至少包含 `request_id`、设备标识、执行状态和设备当前状态。后端只接受与目标设备和请求 ID 匹配的回执；超时、否定回执、过期命令或重复请求都不能被报告为成功。

控制发布使用 QoS 1。`request_id` 由后端生成并在重复请求时复用，设备端应将最近处理的请求做幂等去重。连接异常通过 availability/Last Will 反映为离线。

## 5. 联调顺序

1. 先以 `HOME_DEVICE_ADAPTER=simulated` 验证查询、控制、场景和安全拦截；
2. 启动 Broker，确认后端 MQTT 客户端连接成功；
3. 启动 ESP32，检查 availability 为 online；
4. 监听 telemetry，确认传感器数据格式和房间/设备标识；
5. 通过 `/api/v1/home/devices/{device_id}/state` 下发单设备命令，核对串口日志、ack 和后端状态；
6. 依次验证 sleep、away、movie 场景；
7. 断开 Wi-Fi/Broker，确认离线、超时和恢复行为；
8. 记录 Broker 地址、认证/TLS、固件提交、Arduino 库版本、板卡和接线版本。

## 6. 故障排查

| 现象 | 检查 |
|---|---|
| 设备列表显示离线 | Broker 地址、Topic、availability 和 Last Will |
| 命令已发布但无 ack | 设备订阅主题、JSON 字段、request_id 和 QoS |
| ack 被拒绝 | 设备 ID、房间、request_id、状态字段是否匹配 |
| 重复动作 | 后端/设备是否按 request_id 做幂等 |
| 控制被安全拦截 | 注册表、在线状态、动作白名单、TTL 和设备类型 |
| ESP32 重启 | 风扇独立 5V 供电、共地、驱动器和电源余量 |

## 7. 安全边界

不在模型提示词、前端日志或公共文档中放置 MQTT 密码、TLS 私钥、任意 Topic 或任意 GPIO。ESP32 原型只接低压 LED 和 5V 风扇，禁止接入 220V 市电。

实现参考：[Paho MQTT Python Client](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)、[OASIS MQTT 3.1.1](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html) 和 [ESP-IDF MQTT](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/protocols/mqtt.html)。
