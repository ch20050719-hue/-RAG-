# MG90S 安全闭环二次开发记录

## 研究目标与改造边界

本轮工作支撑论文中的“固定工具与设备安全闭环”：大模型只选择应用层已定义的门体开/关工具；后端完成设备注册、类型、在线、权限、有效期和 `request_id` 校验；受控协议桥关联网络请求与 MCU 本地递增 ID；STM32 仅执行固定端点并返回可审计的控制器状态。固件不接受 GPIO、任意 Topic、脉宽或舵机角度输入。

本次只修改 `stm32/servo_door` 的独立 STM32F103C8T6 低压台架工程，不把旧 `程序` 目录的 C6/Gizwits 固件和 C8 舵机工程混合。工程的 `Door` 纯 C 状态机、ARM、短期限、单调 ID 和失效关闭路径已存在，故以增量扩展和可复现构建为主，而不是引入 HAL、RTOS 或新的通信依赖。

## 调研结论与选型

- TowerPro 产品页确认 MG90S 为舵机并注明需要外部电源，但网页没有发布 PWM 输入阈值或控制脉宽。网页列出的电源/扭矩规格本身也存在不同电压值；第三方镜像的厂商数据表给出约 1.0/1.5/2.0 ms 的控制脉宽基准。基于差异，代码只采用 1 µs 定时器量化、20 ms 帧和 1000–2000 µs 的保守编译包络，不把名义端点当作机械安全范围。来源：[TowerPro MG90S 产品页](https://towerpro.com.tw/product/mg90s-3/)、[MG90S 数据表副本](https://components101.com/sites/default/files/component_datasheet/MG90S-Datasheet.pdf)。
- 保留现有 TIM2_CH1 硬件 PWM 和独立校准常量。它们满足 C8T6 上的确定性输出，且没有新增运行时分配和第三方依赖。Arm 官方 `fromelf` 用于生成 HEX 与裸 BIN：[Arm Compiler 参考](https://developer.arm.com/documentation/101754/0617)。
- 精度声明限制为**目标脉宽按 1 µs 计数**。MG90S 内部死区、齿隙、供电和机械装配决定实际轴角；产品没有向 MCU 输出位置测量值，本固件不声称角度准确度或门体到位。

## 实现内容

### 1. MG90S 定时与校准包络

文件：`board.c`、`board.h`。

- HSI 标称 8 MHz，TIM2 预分频为 7，计数器时钟为标称 1 MHz，即每计数 1 µs；自动重装值 19999，对应 20 ms / 50 Hz。
- PA0 / TIM2_CH1 输出舵机信号。启动、复位、ARM 前及超时后关闭 PWM；OPEN/CLOSE 仍映射到两个固件本地端点。
- 配置中心 1500 µs，OPEN 1600 µs，CLOSE 1400 µs，宏编译检查要求端点不同且处于 1000–2000 µs 包络内。两个默认端点只是无连杆台架起始值；安装方向、复制品差异和连杆行程仍要逐台校准。
- 对非法内部 target 值按 OFF 处理，避免未知枚举意外驱动关闭端点。

### 2. 只读状态回执

文件：`protocol.c`、`protocol.h`、`tests/test_protocol.c`。

新增 `<request_id> STATUS 0`，输出 `PROTO=1`、ARM 标志、目标枚举及 ARM/动作剩余毫秒。新查询消耗严格递增的本地 ID；重复最近一次相同 STATUS ID 返回查询当下快照，不改变目标、不刷新期限。回执中的 `TARGET=OPEN/CLOSE` 是命令状态，不能上报成传感器状态或实际位置。

这让后续桥接服务可以把 MCU 快照映射为带 `request_id` 的控制器报告状态，同时保留“控制器接受目标”与“实测门体状态”的证据边界。协议版本号预留后续能力协商；模型侧仍仅可调用固定门锁工具，不能直接发 STATUS 串口帧或任意舵机目标。

### 3. 原始固件构建

文件：`build_ac6.cmd`、`servo_door.sct`。

脚本清理上次 AXF/HEX/BIN 后，编译 C11/Cortex-M3/microlib 固件，链接到 `0x08000000` 起始的 64 KB Flash 布局，并生成 `.axf`、`.hex`、`.bin`。检查 HEX/BIN 存在且 BIN 不超过 65536 字节，避免编译失败后旧镜像仍看起来像本轮产物。原始 BIN 不携带地址；烧录器必须指定基址 `0x08000000`。

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| TDD：先加入 STATUS 测试再实现协议 | 新功能测试先失败，完成 parser/formatter 后转绿 |
| STM32 协议主机测试 | MSVC 14.44 `/W4 /WX /std:c11`；覆盖未使能/运行/到期状态、重复 STATUS 快照、最大 uint32 ID 和既有期限/重放边界；通过 |
| 智能家居后端回归 | 115 项通过，1 项 pytest 配置警告（环境不识别 `asyncio_mode`） |
| Arm 交叉构建 | Arm Compiler 6.7 / MDK Lite；AXF、HEX、BIN 生成成功 |
| 镜像核验 | BIN 3248 字节；初始栈指针 `0x20005000`，复位向量 `0x08000257`；Flash 基址 `0x08000000` |
| `git diff --check` + 修改文件空白扫描 | 两项均通过；STM32 目录目前在父仓库中为未跟踪目录，因此额外逐行检查了本轮 C/H/CMD/MD 文件 |
| 前端 `npm run build` | 沙箱内因 Vite/esbuild 子进程 `spawn EPERM` 失败；权限提升重跑被拒绝，故未验证 |
| ST-Link 烧录、PA0 示波器波形、MG90S 供电/电平和机械行程 | 未执行；不能标记为硬件兼容验收通过 |

本轮生成的 `build/servo_door.bin` SHA-256：

```text
7C3C0709488091265022FA89761F34AEBF52B826B34CF6081C0E0F492CEAF49C
```

## 实板验收与剩余工作

1. 使用限流稳压 5 V 舵机独立电源，按该只 MG90S 的实物资料选择电流余量；与 STM32 共地，禁止从 MCU 3.3 V 引脚给舵机供电。先断开舵机连杆，并准备切断外部舵机电源。
2. 用示波器测 PA0 的 20 ms 周期和默认 1600/1400 µs 高脉宽，并确认启动、仅 ARM 和期限到期时无驱动脉冲。
3. 验证该只舵机是否识别 PA0 的 3.3 V 高电平。TowerPro 未公布输入高门限；如信号不可靠，增加 3.3 V 输入兼容、5 V 供电的缓冲器后复测。
4. 空载从端点中间逐步校准，记录本机 `SERVO_OPEN_US` / `SERVO_CLOSE_US`、电源、连杆和测量角度；任何机械抵挡、持续嗡鸣或电流异常时立即断电。
5. 协议桥后续应处理 MQTT 绝对过期时间、QoS 1 重复投递、网络 UUID 到 MCU 递增 ID 的映射、MCU 复位后的会话清理、迟到 ACK 匹配及 STATUS 状态归一化。当前固件 TTL 只从 MCU 收到完整串口命令时起算，不可替代网络过期校验。

µVision 工程当前没有选定可用的 STM32F1 Flash 下载算法；这不影响 AXF/HEX/BIN 生成。通过 Keil 下载时应在实际安装的 STM32F1 DFP 中选择与芯片匹配的算法；通过 ST-Link/STM32CubeProgrammer 写裸 BIN 时必须显式指定 `0x08000000`。本轮没有运行烧录器。
