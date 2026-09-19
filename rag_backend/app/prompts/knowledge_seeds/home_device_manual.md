# 智能家居设备说明书（种子知识）

## 桌面原型设备

### desk_light（书桌灯）
- 类型：light
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 联调说明：STM32F103C8T6 通过 MOSFET/继电器控制低压 USB 灯，不接 220V

### desk_fan（书桌风扇）
- 类型：fan
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 联调说明：5V USB 小风扇 + MOSFET/继电器，禁止市电

### window_motor（窗户执行器）
- 类型：window
- 房间：study
- 动作：固定状态 open / closed
- 硬件目标：28BYJ-48 + 专用驱动模块，步数、方向和限位需实机校准

## 传感器

| 传感器 | ID | 单位 | 说明 |
|---|---|---|---|
| 温度 | room_temp | celsius | DHT11 |
| 湿度 | room_humidity | percent | DHT11 |
| 光照 | room_light | lux | 光敏电阻 ADC 映射值 |
| 实验烟雾 | room_smoke | raw | MQ-2 ADC 映射值，不是消防级浓度 |

## 模式与阈值

- `manual` / `automatic` 是版本三阈值联动模式；手动模式保留报警但不自动覆盖设备状态。
- `normal` / `sleep` / `away` 是云端场景配置，与手动/自动模式相互独立。
- 可调阈值固定为温度上限、湿度上限、光照下限和实验烟雾上限；必须通过范围校验。

## 控制原则

1. 只能控制已注册设备；
2. 灯/风扇只允许 on/off，窗户只允许 open/closed，门锁必须走专用工具；
3. 状态以设备回执为准；
4. 设备离线或命令过期时拒绝执行。
