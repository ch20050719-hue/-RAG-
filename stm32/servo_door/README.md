# STM32F103C8T6 舵机门台架工程

## 范围与文件

仅用于低压台架上的普通位置舵机。HSI 标称 8 MHz，PA0 输出 TIM2_CH1 的 50 Hz PWM；USART1 使用 PA9/PA10、115200、8N1。无 HAL、CMSIS、RTOS、外部晶振或在线下载依赖。标准 C 库由已安装的 Arm Compiler 提供。

文件：`servo_door.uvprojx`（Keil 工程）、`servo_door.sct`（64 KB Flash / 20 KB RAM 布局，预留 2 KB 栈）、`startup.c`（复位入口和完整中容量向量表；Arm C 运行库负责初始化后进入 main）、`board.c/.h`（寄存器和校准）、`main.c`（串口循环）、`protocol.c/.h`（纯协议状态机）、`tests/test_protocol.c`、`tests/run.cmd`（主机测试）、`build_ac6.cmd`（离线命令行构建）。

本轮 MG90S 选型依据、研究映射、代码修改及验证记录见 [DEVELOPMENT_RECORD.md](DEVELOPMENT_RECORD.md)。

目录导航：[接线](#接线) · [构建与烧录](#构建与烧录) · [协议](#协议) · [校准与实板验收](#校准与实板验收) · [验证与限制](#验证与限制)

## 成熟方案调研

- [ST RM0008 官方参考手册](https://www.st.com/resource/en/reference_manual/rm0008-stm32f101xx-stm32f102xx-stm32f103xx-stm32f105xx-and-stm32f107xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)：采用 RCC、GPIO、TIM2、USART 的寄存器配置。网页工具未能完整提取大 PDF；寄存器与时序仍需实板验证。
- [Arm 官方 Cortex-M3 启动示例](https://github.com/ARM-software/CMSIS_5/blob/develop/Device/ARM/ARMCM3/Source/ARM/startup_ARMCM3.s)：参考向量表与复位职责；本工程独立实现 C 启动文件，不复制或依赖 CMSIS 文件。
- [TowerPro MG90S 产品页](https://towerpro.com.tw/product/mg90s-3/)：用于确认 MG90S 供电和舵机规格；厂家要求外部电源。产品页没有给出控制脉宽，故脉宽基准另参考[厂商数据表副本](https://components101.com/sites/default/files/component_datasheet/MG90S-Datasheet.pdf)，并通过实物校准确定实际端点。
- [Arm Compiler `fromelf` 参考手册](https://developer.arm.com/documentation/101754/0617)：用工具链自带转换器由 AXF 生成 HEX 与 BIN，避免增加额外转换依赖。
- [Keil 自定义 scatter 配置](https://www.keil.com/support/man/docs/uv4/uv4_dg_adsld.asp)：关闭自动内存布局，显式指定本地 scatter。采用工具链内置 microlib；无第三方固件依赖。针对自包含要求编写少量寄存器代码，不引入完整厂商包。

## 接线

| STM32 / 设备 | 连接 |
| --- | --- |
| PA0 | 舵机信号线；建议外加 10 kΩ 下拉，保证复位期间电平明确 |
| PA9 (TX) | USB-TTL 的 RX |
| PA10 (RX) | USB-TTL 的 TX，必须是 3.3 V 逻辑 |
| GND | STM32、串口适配器、舵机电源共地 |
| MG90S 电源 | 独立稳压 5 V 电源；按实物堵转电流留足余量，和 STM32 共地 |
| PA13 / PA14 / GND / NRST | ST-Link SWDIO / SWCLK / GND / NRST |

BOOT0 置 0。不要用 STM32 的 3.3 V 引脚给舵机供电，不要接 RS-232 电平或市电。MG90S 厂家要求外部供电；STM32 PA0 输出 3.3 V 控制信号，厂家未公布输入高电平阈值，需先验证该只舵机能可靠识别；不能可靠识别时，在 PA0 与信号线间增加 3.3 V 到 5 V 的逻辑缓冲。舵机断开连杆后再首次通电，准备直接切断舵机电源。停止 PWM 不等于切断电源，也不保证门停住、锁住或回到关闭位置。

## 构建与烧录

基准工具链：Keil µVision5 + **Arm Compiler 6.7**（armclang/armlink，C11，Cortex-M3，Thumb，microlib；已用本机 MDK-ARM Lite 5.24 附带版本验证构建）。工程已经设置 `uAC6=1`，不能切换为 Arm Compiler 5 编译本启动文件。其他 AC6 版本需要重新验证。

1. 打开 `servo_door.uvprojx`。在 Options for Target → Target 选择已安装的 Arm Compiler 6.7。
2. 确认 CPU 为 Cortex-M3，IROM `0x08000000/0x10000`，IRAM `0x20000000/0x5000`，晶振栏为 8 MHz（运行时实际使用 HSI）。
3. Linker 页关闭 Use Memory Layout from Target Dialog，Scatter File 为 `servo_door.sct`。不要添加第二个厂商 startup 或 SystemInit 文件。
4. 执行 Rebuild，输出到 `build/servo_door.axf`、`build/servo_door.hex`。命令行脚本 `build_ac6.cmd` 另外输出可烧录原始映像 `build/servo_door.bin`。
5. 若 µVision 提示器件数据库缺少 STM32F103C8，使用本机已有的 Cortex-M3 器件定义并保留上述内存设置，或离线安装 STM32F1 器件支持包。源码构建不依赖该包；调试器/Flash 算法可能需要已安装的支持包。
6. Debug 选择实际 ST-Link、SWD；Utilities → Settings → Flash Download 检查是否已从 STM32F1 DFP 选中下载算法。Keil STM32F1 DFP 2.2.0 将 STM32F103C8 映射到 `STM32F10x_128.FLM`；这是该 DFP 的算法名称/覆盖范围，不会改变芯片本身 64 KB Flash 的规格。本工程链接布局限制在 64 KB，当前程序约 7 KB。连接实板后再 Download；工程不会自动烧录。

不用 IDE 的离线构建（需要已有且许可可用的 AC6）：

```bat
set "ARMCLANG_BIN=C:\Keil_v5\ARM\ARMCLANG\bin"
build_ac6.cmd
```

本工程已用 MDK Lite 附带 Arm Compiler 6.7 执行命令行构建。`.bin` 是从 `0x08000000` 开始的原始映像，烧录工具需将目标地址设为 `0x08000000`；`.hex` 含地址记录，`.axf` 保留调试符号。构建脚本会拒绝超过 C8T6 64 KB Flash 的 BIN。命令行构建不等同于实际烧录或板上验收。

复位向量进入 `Reset_Handler`，再调用 Arm C 运行库 `__main`，由运行库按 scatter 文件完成 RW/ZI 初始化并进入 main；工程不使用堆、C++ 构造器或半主机 I/O。Flash 地址从零启动映射到 `0x08000000`；不支持带偏移的 bootloader 跳转。

## 协议

主机采用一问一答：收到完整回执后再发下一行。ASCII 大写，字段之间恰好一个空格，以 LF 或 CRLF 结束。单行最多 63 字节（不含 CRLF）；超长、控制字符、串口溢出/帧错误会丢弃整行直到 LF，回复 `ERR 0 BAD_LINE`。不完整行不会执行。

```text
<request_id> <ARM|OPEN|CLOSE|DISARM|STATUS> <ttl_ms>
```

`request_id` 为 1..4294967295 的十进制数。每次启动后的新请求必须严格递增。ARM/OPEN/CLOSE 的 TTL 为 100..5000 ms；DISARM 和只读 STATUS 的 TTL 必须为 0。

```text
READY PWM_DISABLED
1 ARM 5000
ACK 1 ARMED
2 OPEN 1000
ACK 2 TARGET_OPEN_COMMANDED
3 CLOSE 1000
ACK 3 TARGET_CLOSE_COMMANDED
4 DISARM 0
ACK 4 PWM_DISABLED
5 STATUS 0
ACK 5 STATE PROTO=1 ARM=0 TARGET=OFF ARM_LEFT_MS=0 ACTION_LEFT_MS=0
```

上例需要逐行发送，OPEN/CLOSE 间等待应短于 1000 ms；若动作已到期，需用新 ID 再次 ARM。上电、复位无 PWM，ARM 自身也不产生 PWM；再次 ARM 会先停止当前 PWM。只有在 ARM 有效期内才能接受 OPEN/CLOSE。

TTL 从**本机收到完整有效行**的时刻开始计时，是本地使能/脉冲保持期限，不是网络消息的截止时间。动作到期或者 ARM 到期，任何一个先发生都会关闭 PWM 并撤销 ARM。新动作不会延长原 ARM 期限。毫秒计数支持 uint32 回绕；主循环持续运行时处理到期。

幂等采用“递增 ID 水位 + 最后一条有效请求回执”：重发最后一条相同 ID、命令和 TTL，返回 `DUP <id> <原结果>`，不重新动作、不续期；该回执只描述历史请求结果。相同 ID 不同内容返回 `ERR <id> ID_CONFLICT`；更旧 ID 返回 `ERR <id> ID_STALE`，即使旧记录不在缓存中也不能重新执行。格式合法但未 ARM 的动作返回 `ACK <id> NOT_ARMED`，仍消耗该 ID。语法/数值错误返回 `ERR 0 BAD_REQUEST`，不消耗 ID。ID 用完须复位后重新建立串口会话；复位不保存去重状态，桥接端必须清空旧请求，禁止盲目重放。

`STATUS` 是只读查询，也消耗新的递增 ID，回报 `PROTO`、ARM 标志、控制目标及两个剩余期限。重复最近一次相同 STATUS ID 返回 `DUP` 前缀和**查询当下**状态；它不会刷新 TTL 或改变目标。`TARGET=OPEN/CLOSE` 仅为软件下发目标，绝不表示舵机或门体已实测到位。

ACK 的 `TARGET_*_COMMANDED` 只表示已下发目标脉宽，不表示舵机已转到位或门已开/关。没有位置传感器。ARM 是台架操作使能，不是身份认证，也不是生产安全互锁。串口应仅连接可信的本地调试主机。

## 校准与实板验收

TowerPro MG90S 数据表副本给出约 1000/1500/2000 µs 对应约 -90°/0°/+90°；厂家网页标示死区 1 µs，而数据表副本标示 5 µs，存在来源差异。固件 TIM2 以 1 µs 计数，周期 20 ms（50 Hz）；输出量化到 1 µs 不等于轴角精度或位置反馈。当前 OPEN=1600 µs、CLOSE=1400 µs 是脱离连杆时的保守起始值，名义约为中位两侧各 18°，不是 MG90S 全行程，也不是标定结果。编译期限制校准脉冲在 1000..2000 µs，并确保两个端点不相同；按各自连杆安全行程逐步调整 `board.h` 后重编译。

1. 拆开机械连杆，先不接舵机信号，用示波器确认上电、仅 ARM、复位时 PA0 无周期脉冲。
2. 发 OPEN，测周期约 20 ms、脉宽约 1600 µs；CLOSE 约 1400 µs；检查 TTL 到期和 DISARM 后 PA0 拉低。
3. 接上无负载舵机，从中位附近逐步调整，每次建议 20–50 µs。听到持续堵转声、碰到端点或电流异常时立即断舵机电源。确定方向后记录最终 OPEN/CLOSE 数值。
4. 复测未 ARM 拒绝动作、重复请求不续期、旧 ID 拒绝、断开串口后 TTL 到期、超长/乱码后下一条正确命令可以恢复。
5. 最后装回轻载连杆，复测运动范围与供电跌落。无传感器、无独立硬件急停/看门狗的本项目不能用于真实门禁安全控制。调试暂停或 CPU 卡死时定时器可能继续输出，直接断电才是可靠的台架停机手段。

## 验证与限制

主机测试（MSVC Native Tools 环境）：

```bat
call E:\vs\VC\Auxiliary\Build\vcvars64.bat
tests\run.cmd
```

也可用 GCC/Clang：`cc -std=c11 -Wall -Wextra -Werror -I. tests/test_protocol.c protocol.c -o test_protocol`，然后运行程序。

2026-09-25：MSVC 14.44 在 `/W4 /WX /std:c11` 下编译并运行通过，新增覆盖 STATUS 状态快照、期限剩余值、重复查询和到期行为。主机测试覆盖纯 C 状态机，不模拟寄存器硬件；尚未测量覆盖率。Arm Compiler 6.7 命令行构建和 HEX/BIN 输出已验证；Flash 烧录、PWM 波形、PA0 电平阈值与实板串口尚未验证，不能据此声称硬件验收通过。

HSI 有温漂与器件误差；8 MHz 下 BRR=69，标称实际波特率约 115942（+0.64%），还需叠加 HSI 误差。若乱码，先检查共地、逻辑电平及波形。

**MQTT 未集成，UART 桥接层待实现。** 后续桥必须负责用户鉴权、设备注册/在线校验、网络绝对过期时间、队列陈旧消息清理、网络 request_id 到本地递增 ID 映射与复位握手。此固件的 TTL 不能识别在网络中滞留的消息，不能直接替代上层控制契约。
