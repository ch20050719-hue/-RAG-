# 智能家居设备说明书（种子知识）

## 桌面原型设备

### desk_light（书桌灯）
- 类型：light
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 联调说明：ESP32 GPIO 控制 LED，仅低压演示，不接 220V

### desk_fan（书桌风扇）
- 类型：fan
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 联调说明：5V USB 小风扇 + MOSFET/继电器，禁止市电

## 传感器

| 传感器 | ID | 单位 | 说明 |
|---|---|---|---|
| 温度 | room_temp | celsius | DHT22 |
| 湿度 | room_humidity | percent | DHT22 |
| 光照 | room_light | lux | BH1750 |
| 人体 | room_motion | bool | HC-SR501，0/1 |

## 控制原则

1. 只能控制已注册设备；
2. 只能使用固定动作 set_state；
3. 状态以设备回执为准；
4. 设备离线或命令过期时拒绝执行。
