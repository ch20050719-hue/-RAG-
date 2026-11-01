# MQTT / 机智云联调说明

本文档描述后端、受控协议桥、ESP8266 Wi-Fi 模块和 STM32F103C8T6 版本三硬件之间的联调边界。默认开发模式为 `simulated`；只有准备好 Broker、机智云产品、固件和低压硬件后，才切换 `mqtt`。

ESP8266 负责网络与机智云连接，STM32 通过 UART 与 ESP8266 交换传感器数据和控制回执。机智云数据点不能直接暴露给 Agent，必须映射为内部固定设备命令。

## 1. 后端配置

```text
HOME_DEVICE_ADAPTER=mqtt
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=home-backend
MQTT_ACK_TIMEOUT_SECONDS=5
```

本地演示可以使用 Mosquitto。生产或跨网络联调必须启用账号、ACL、TLS 和最小权限 Topic 授权。

## 2. 内部 Topic 契约

```text
home/v1/{room}/{device_id}/state/set       后端 → 设备：LED/风扇/水泵/蜂鸣器命令
home/v1/{room}/{device_id}/state/ack       设备 → 后端：普通状态回执
home/v1/{room}/{device_id}/door/set        后端 → 舵机门体：开门/关门
home/v1/{room}/{device_id}/door/ack        舵机门体 → 后端：门体动作回执
home/v1/{room}/{device_id}/telemetry       设备 → 后端：温湿度/烟雾/火焰/有人数据
home/v1/{room}/{device_id}/availability    设备 → 后端：online/offline
```

版本三示例：

```text
home/v1/study/desk_light/state/set
home/v1/study/desk_fan/state/set
home/v1/study/sprinkler_pump/state/set
home/v1/study/alarm_buzzer/state/set
home/v1/study/door_lock/door/set
home/v1/study/room_sensors/telemetry
```

Topic 只是适配器内部协议。前端和 Agent 只能调用固定 API/工具，不能提交 Topic、GPIO、机智云数据点名或任意动作。

## 3. 消息与回执

普通开关命令：

```json
{
  "request_id": "uuid",
  "action": "set_state",
  "state": "on",
  "expires_at": "2026-09-20T12:00:00+00:00"
}
```

门锁业务 API 具有固定动作白名单，例如 `unlock`、`lock`、`open_door`、`close_door`；但当前 MQTT 固件契约仅实现 `open_door`、`close_door`。因此，`HOME_DEVICE_ADAPTER=mqtt` 时后端拒绝锁舌/反锁状态动作，不会只更新软件状态并声称硬件已锁定。MQTT 门体回执必须显式包含 `request_id`、`device_id`、`action`、布尔 `accepted` 和 `ack_status`；缺字段的回执被忽略并等待超时。门体动作仅在 `accepted=true` 且 `ack_status=success` 时记为控制器确认完成；控制器没有位置传感器时，该确认仍不等于实测门体到位。要恢复真实门磁/锁舌状态，还需由协议桥上报可信状态字段；目前软件状态不会跨后端重启恢复。

控制发布使用 QoS 1。QoS 1 是至少一次传递，接收端可能收到重复消息，不能据此推断设备动作只执行一次（见 [OASIS MQTT 3.1.1 §4.3.2](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)）。后端在 `DeviceService` 边界把 `request_id` 绑定到统一命令指纹：跨普通设备与门锁控制域复用不同命令会拒绝；已完成的相同 ID、相同命令重放首次回执；同 ID 命令正在等待 ack 时不再次发布。普通设备的成功 ack 还必须匹配请求中的目标状态，否则后端不会更新设备状态，并在等待超时后允许同指纹重试。若门体 ack 超时且没有完成回执，后端不缓存为最终失败，允许以同 ID、同指纹重试；设备端/协议桥必须自行去重，否则可能重复执行。后端缓存也不跨进程或重启持久化。连接异常通过 availability/Last Will 反映为离线。

普通设备回执必须显式包含 `state`，并与请求目标匹配；缺少 `state` 时即使目标为 `off` 也不能被当作成功。普通执行器指纹字段为 `device_id + action + state`；门锁动作另绑定授权、二次确认和 TTL 参数。Agent 工具 schema 不接受授权或二次确认参数；需授权的门锁操作经登录保护的家居 API 执行。TTL 的绝对过期时间不参加普通命令指纹，因此同一逻辑命令在客户端重试时仍匹配；过期校验仍在每次发布前执行。

## 4. 联调顺序

1. 使用 `HOME_DEVICE_ADAPTER=simulated` 运行软件回归，确认五类传感器和五类设备注册正确；
2. 启动 Broker，确认后端 MQTT 客户端连接和权限；
3. 启动 ESP8266 与 STM32，确认机智云数据点映射、UART 和 availability；
4. 上报温度、湿度、烟雾、火焰和有人数据，核对单位、有效范围、时间戳和质量；
5. 通过 `/api/v1/home` 固定 API 验证 LED、风扇、喷淋水泵、蜂鸣器和门锁回执；
6. 分别验证手动模式和自动模式：温度/烟雾启风扇和蜂鸣器，火焰启水泵和蜂鸣器，有人开 LED；
7. 验证密码、IC 卡和 APP 解锁均经过门锁认证服务，不允许绕过 `door_lock` 安全链路；
8. 断开 Broker 或设备，确认离线、超时、恢复和重复请求行为；
9. 记录 Broker、固件、机智云产品/数据点、模块、板卡和接线版本。

## 5. 故障排查

| 现象 | 检查 |
|---|---|
| 设备离线 | Broker、鉴权、availability、UART 和 Last Will |
| 命令已发布但无 ack | 订阅 Topic、JSON 字段、request_id、QoS 和固件日志 |
| ack 被拒绝或忽略 | 房间、设备、动作、状态和请求 ID 是否匹配 |
| 重复动作 | 后端和设备端是否按 request_id 幂等 |
| 自动联动不执行 | 当前是否为 automatic、传感器质量和阈值是否合法 |
| STM32/ESP8266 重启或执行器抖动 | 独立供电、共地、电源余量、驱动器和信号线 |

## 6. 安全边界

不在提示词、前端日志或公共文档中放置机智云密钥、MQTT 密码、TLS 私钥、任意 Topic 或 GPIO。STM32 原型只接低压 LED、5V 风扇、喷淋泵、蜂鸣器和舵机门锁，禁止接入 220V 市电。

当前 MQTT 适配器和软件回归只证明协议校验与模拟闭环通过；真实 Broker、机智云、ESP8266、STM32 固件和接线仍需现场联调记录。
