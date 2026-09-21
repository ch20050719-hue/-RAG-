# 智能家居设备说明书（版本三知识种子）

## 控制器与通信

- 主控：STM32F103C8T6。
- Wi-Fi 通信：ESP8266，通过 UART 与 STM32 交换数据和固定命令。
- 云平台：机智云。
- 本地显示：OLED。

## 执行器

### desk_light（LED 灯）
- 类型：light
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 用途：手动照明；自动检测到有人时开启。

### desk_fan（风扇）
- 类型：fan
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 用途：温度过高时降温；烟雾超限时通风。

### sprinkler_pump（喷淋水泵模拟装置）
- 类型：water_pump
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 用途：检测到火焰时自动启动；仅使用低压模拟装置。

### alarm_buzzer（报警蜂鸣器）
- 类型：buzzer
- 房间：study
- 动作：set_state（on / off）
- 默认安全状态：off
- 用途：温度、烟雾或火焰报警。

### door_lock（舵机门锁）
- 类型：door_lock
- 房间：study
- 控制方式：专用门锁动作
- 开锁方式：密码、IC 卡、APP 授权
- 约束：不能通过通用设备开关接口控制。

## 传感器

| 传感器 | ID | 类型 | 说明 |
|---|---|---|---|
| 温度 | room_temp | temperature | 温度数值 |
| 湿度 | room_humidity | humidity | 湿度百分比 |
| 烟雾 | room_smoke | smoke | 实验烟雾模拟量，不是消防级浓度 |
| 火焰 | room_flame | flame | 0 表示未检测到，1 表示检测到 |
| 是否有人 | room_presence | presence | 0 表示无人，1 表示有人 |

## 模式与阈值

- `manual`：按键或 APP 直接控制风扇、LED、舵机门锁和喷淋水泵。
- `automatic`：按固定规则执行风扇、蜂鸣器、水泵和 LED 联动。
- 场景预设：`normal` 不改变设备状态；`sleep` 关闭 LED 并尝试反锁；`away` 关闭 LED/风扇并尝试锁门。
- 场景预设与手动/自动模式相互独立，场景失败必须返回逐动作回执。
- 场景人工工具矩阵：`normal` 允许 LED、风扇、水泵、蜂鸣器、阈值、模式和门锁；`sleep` 允许 LED、风扇、蜂鸣器和门锁；`away` 允许水泵、蜂鸣器和门锁。环境查询、状态查询、场景切换和 automatic 安全联动始终保留。
- 可调阈值固定为温度上限、湿度上限和实验烟雾上限。
- 火焰和有人是状态型检测，不作为普通数值阈值处理。

## 控制原则

1. 只能控制已注册设备；
2. 风扇、LED、水泵和蜂鸣器只允许 `on/off`；
3. 门锁必须走专用动作和授权流程；
4. 状态以设备回执为准；
5. 设备离线、命令过期或参数非法时拒绝执行；
6. Agent 不得接收 GPIO、寄存器、任意 Topic 或机智云底层数据点。
