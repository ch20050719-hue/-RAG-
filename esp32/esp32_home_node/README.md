# ESP32 桌面原型节点

## 功能

- 连接 Wi-Fi 与 MQTT Broker
- 订阅 `home/v1/study/desk_light/state/set` 与 `home/v1/study/desk_fan/state/set`
- 发布回执 / 遥测 / 在线状态
- 控制 LED 与 5V 风扇
- 上报 DHT22 温湿度、BH1750 光照、HC-SR501 人体

## 安全

- 仅低压演示，禁止接入 220V
- 不把 Wi-Fi/MQTT 密码提交到 Git（本地修改 sketch 或使用 secrets 头文件）
- 后端是唯一控制入口；固件不暴露任意 GPIO 命令
- 节点级 Last Will 使用 `home/v1/study/availability`，异常断线时后端会将房间设备标记为离线

## 接线建议

| 模块 | ESP32 引脚 | 说明 |
|---|---|---|
| LED + 220Ω | GPIO25 → LED → GND | 灯 |
| MOSFET/继电器 | GPIO26 | 风扇 |
| DHT22 | GPIO4 | 温湿度 |
| BH1750 | SDA=21, SCL=22 | 光照 |
| HC-SR501 | GPIO27 | 人体 |

## 烧录

1. 安装 Arduino IDE 与 ESP32 板支持
2. 库：`PubSubClient`、`ArduinoJson 6`、`DHT sensor library`、`BH1750`
3. 修改 sketch 顶部 Wi-Fi/MQTT 配置
4. 选择开发板 `ESP32 Dev Module` 后上传

## 与后端联调

1. 本机或局域网启动 MQTT Broker（如 Mosquitto，端口 1883）
2. 后端配置 `MQTT_HOST` 指向 Broker
3. 切换设备适配器为 `MqttDeviceAdapter`（或调用 `/api/v1/home/*` 时使用 MQTT 服务）
4. 发送开灯指令，检查串口日志与后端回执
