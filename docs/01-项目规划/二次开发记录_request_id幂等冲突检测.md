# 二次开发记录：固定工具与设备安全闭环增强

> 日期：2026-09-25
> 研究方向：固定工具调用、设备状态验证与安全控制
> 适用范围：单房间智能家居模拟设备与 MQTT 软件闭环

## 1. 研究目标与问题

本轮改造围绕论文主线“自然语言意图 → 固定设备工具 → 确定性安全校验 → 设备回执”，强化授权入口、请求幂等、并发状态和设备回执的一致性。对应的研究问题是：同一 `request_id` 被重试或错误复用于不同命令时，系统能否避免第二次副作用；模型是否能通过工具参数伪造用户授权；设备回执是否能证明目标动作完成？

改造前，模拟和 MQTT 适配器以 `request_id` 作为结果缓存键；缓存命中时直接返回第一次回执，没有检查重试命令是否与原命令一致。MQTT 普通执行器对同 ID 的并发请求也会重新创建等待事件并再次发布。门锁服务同样只按 ID 返回缓存结果。Agent 工具还暴露 `authorized` 布尔参数，模型可能将其设为真；普通设备回执不比较应答状态与命令目标；门体执行服务仅看 `accepted`，可能把未成功的 ack 当作动作成功。MQTT 硬件模式下的锁舌/反锁动作也没有底层协议，却会只改内存状态并返回成功。

本轮论点限定为软件控制路径的确定性：同 ID、同命令应得到首次执行回执；同 ID、不同命令应在设备副作用前被拒绝，即使上次暂时失败仍不能改用另一动作；同 ID 在不同设备控制域之间也不得复用；暂时性传输失败允许同指纹重试；模型不能自行声明已获授权；只有显式且与目标命令一致的完成回执才能更新状态；当前 MQTT 固件未实现的锁舌/反锁动作应明确拒绝。当前未据此声称真实硬件具备 exactly-once 执行能力。

## 2. 调研结论与技术选型

MQTT 3.1.1 将 QoS 1 定义为“至少一次”传递，允许重复交付；应用必须自行处理重复消息，不能把 QoS 1 当作单次执行保证。[OASIS MQTT 3.1.1 §4.3.2](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)

成熟参考实现采用“键 + 请求指纹 + 执行状态/回执”的模式。AWS Powertools Python 支持相同输入重放、并发保护和 payload tampering 防护，项目约 3.3k GitHub stars、MIT-0 许可；但其核心面向 Lambda，持久化层面向 DynamoDB、Redis 等，与本项目同步适配器和设备协议边界不完全匹配。[实现文档](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/)、[GitHub 项目](https://github.com/aws-powertools/powertools-lambda-python)

评估过的 Python 包中，`pyidempotent` 0.1.0 标注 MIT、Beta、单维护者，PyPI 发布日期为 2026-06-05，其 PyPI 页面指向的 GitHub 仓库当前返回 404；`exactly-once` 标注 MIT、Alpha、单维护者，2026-08-28 发布，针对 Agent 副作用但仍处于早期阶段。[pyidempotent](https://pypi.org/project/pyidempotent/)、[exactly-once](https://pypi.org/project/exactly-once/)

**选型：不引入第三方依赖。** 复用现有适配器的进程内回执缓存，增加规范化命令指纹与锁保护。它适合目前的单实例模拟验证，且不增加 Redis、数据库或新的运行时依赖；代价是缓存不跨进程或重启持久化。IETF Idempotency-Key 工作草案建议对不同 payload 的键复用返回冲突、对相同键的在途请求返回处理中，本实现采用相同语义，但不声称项目遵循该草案的 HTTP 状态码契约。[IETF 工作草案](https://github.com/ietf-wg-httpapi/idempotency/blob/main/draft-ietf-httpapi-idempotency-key-header.md)

授权选型采用服务端信任边界：Agent 固定工具不接收 `authorized` 或 `confirmed` 字段，Agent 不能通过工具参数提升权限；需授权的动作走已有登录保护的家居 API，并由 API 层提供授权标记。这样保留经认证用户的明确控制入口，不把模型生成内容当作身份凭据。

## 3. 实现思路

每条命令先规范化其业务字段并计算等价指纹，再按以下规则处理：

| 请求状态 | 处理方式 | 设备副作用 |
|---|---|---|
| ID 未使用 | 校验设备/命令并执行，保存指纹和结果 | 本次在途执行只发布一次 |
| ID 已完成且指纹相同 | 返回首次回执 | 不重复执行/发布 |
| ID 已使用但指纹不同 | 返回冲突拒绝 | 不执行/发布 |
| ID 相同且仍等待 MQTT ack | 返回处理中拒绝 | 不再次发布 |
| ID 相同且此前遇到暂时性传输失败 | 不缓存为最终结果，同指纹可重试 | 可能再次发布，设备端必须去重 |

普通设备命令指纹由 `device_id + action + state` 组成；门锁动作指纹还绑定授权、确认和 TTL 秒数。`DeviceService` 在服务边界统一普通设备和门锁动作的 `request_id` 命名空间，避免相同 UUID 在两套子缓存间复用。普通命令的绝对过期时间不放入指纹，因为重试会重新生成时间戳；适配器仍会在每次发布前校验本次命令 TTL。

普通 MQTT ack 必须显式包含状态并匹配待处理指纹中的设备、动作和目标状态。收到 `accepted=true` 但状态不一致或缺少状态的回执时不更新状态并继续等待，最终按 ack 超时返回失败；相同指纹可以重试。门体 ack 必须显式包含 `device_id` 与 `ack_status`，身份或状态缺失/错配时不接受；只有 `accepted=true` 且 `ack_status=success` 才视为控制器报告动作完成。门锁服务将临时 MQTT 传输/超时和设备离线异常返回给调用者，但不把它写入完成结果缓存；仍保留本次 ID 的指纹，禁止在超时后将同 ID 改为另一动作。门磁和在线等安全状态的更新与动作执行使用同一把锁，避免本地检查期间被并发更新。

## 4. 关键代码修改

改动位于本地 `financial_rag/` 目录（该目录被仓库根 `.gitignore` 忽略，见“工作区说明”）：

- `financial_rag/rag_backend/app/home_automation/simulated_device.py`：增加冲突/处理中异常、指纹匹配函数及线程锁；普通开关和模拟舵机执行都绑定指纹，完全相同的重复请求重放原回执。
- `financial_rag/rag_backend/app/home_automation/mqtt_adapter.py`：记录已完成及在途命令指纹；同 ID、不同命令拒绝，同 ID、同命令在途时拒绝重复发布，避免替换 ack 等待事件。
- `financial_rag/rag_backend/app/home_automation/device_service.py`：在服务层统一普通设备和门锁控制的请求指纹命名空间，拒绝跨控制域 ID 复用。
- `financial_rag/rag_backend/app/home_automation/door_lock.py`：门锁命令缓存绑定动作、授权、二次确认和 TTL；同一锁保护状态更新和动作检查；暂时性执行器错误可用同 ID、同指纹重试，但不能改动作；仅成功完成的 ack 更新门体状态。
- `financial_rag/rag_backend/app/home_automation/simulated_device.py`、`mqtt_adapter.py`：标注模拟/硬件适配能力差异；MQTT 缺少锁舌/反锁动作协议时由门锁服务拒绝请求，模拟适配器仍可演示逻辑状态机。
- `financial_rag/rag_backend/app/home_automation/device_tools.py`、`financial_rag/rag_backend/app/multi_agent_system/agents/home_specialist.py`：从 Agent 工具 schema 移除授权/二次确认布尔字段，Agent 请求不再将用户意图等同于授权；授权动作通过登录保护的设备 API。
- `financial_rag/rag_backend/tests/unit/test_home_automation_simulator.py`：新增普通设备与模拟门动作的 ID 冲突用例。
- `financial_rag/rag_backend/tests/unit/test_home_automation_service.py`：新增跨设备/门锁 ID 冲突、门体超时同指纹重试、非成功 ack 状态不得更新、并发在线状态更新串行化验证。
- `financial_rag/rag_backend/tests/unit/test_mqtt_adapter.py`：新增普通 ack 缺少/错配状态拒绝、门体 ack 缺少/矛盾状态拒绝、MQTT 不支持门锁逻辑动作，以及已有回执重放、冲突和在途请求不重复发布验证。
- `financial_rag/rag_backend/tests/unit/test_home_automation_tools.py`、`test_home_specialist.py`：验证工具 schema 不暴露授权参数，Agent 意图不会解锁或开门。

拒绝结果沿用现有失败回执/`blocked_reason` 机制；门锁服务内冲突会进入门锁日志。固定工具白名单、设备注册和 QoS 配置不变；增加了回执一致性验证与服务级授权边界。

## 5. 验证与论文可用证据

| 验证 | 结果 | 可支持的结论 |
|---|---:|---|
| 定向安全与幂等测试 | `16 passed` | 覆盖跨域 ID 冲突、超时重试、ack 身份/字段/状态完整性、工具授权边界、并发状态更新和 MQTT 能力拒绝 |
| 后端家居/安全回归：模型、服务、模拟器、工具、环境、MQTT、API、Agent、路由、任务调度 | `115 passed`, 1 config warning | 固定工具、设备控制、环境与安全回归通过；pytest 提示当前插件不识别 `asyncio_mode` 配置项 |
| 项目 README 所列家居与安全回归集 | `120 passed`, 1 config warning | 覆盖设备、工具、路由、环境、MQTT、会话、限流与工具授权相关测试 |
| 根仓库 `git diff --check` + 本轮文件空白检查 | 通过 | 跟踪文件差异无空白错误；另对本轮所有源码、测试与文档文件扫描，未发现行尾空格。`financial_rag/` 被根 `.gitignore` 排除，故不在 `git diff --check` 的输入内 |
| 前端 `npm run build` | 通过 | Vite 5.4.21 构建成功；存在 Browserslist 数据过期和若干 JS chunk 超过 500 KB 的非致命警告 |

MQTT 测试使用本地假客户端并校验 publish 调用次数，不连接真实 Broker。测试可支持“应用端对相同 request_id 的语义冲突进行拒绝，并阻止无效 ack 推动状态更新”的软件级结论。ack 超时后对同一指纹的请求允许重新发布，因此设备/协议桥仍须按 request_id 去重；本轮测试也不能支持硬件动作无重复、进程重启后去重、网络故障下端到端成功率或实际控制延迟等结论。

建议论文实验报告分别统计：同命令重试回执一致率、不同命令 ID 冲突拒绝率、冲突请求引发的额外 publish 数、在途重试引发的额外 publish 数。当前自动测试覆盖这些判据的代表性用例，但没有运行大样本统计或实机实验；论文应将结果表述为单元/集成边界验证，不外推为统计性能结论。

## 6. 限制与后续工作

- 指纹和回执缓存在单个 Python 进程内，重启、多个后端实例或横向扩展会失去共享记录；若部署范围扩大，应选用共享持久化存储并定义 TTL/清理策略。
- 当前回执缓存沿用既有常驻字典，不做容量清理；长期高频运行前应增加有界保留策略，并确保缓存淘汰窗口大于客户端和设备端的最大重试周期。
- DeviceService 面向 Agent/API 的入口使用统一跨控制域指纹；底层适配器本身仍是内部组件，直接绕过 DeviceService 调用时，其普通设备和门体结果缓存仍分属两个命名空间。
- Agent 对话工具会拒绝授权动作；本轮验证了门锁 API 依赖登录用户，但未做浏览器端二次确认流程或真实用户权限矩阵实验。
- MQTT 门锁状态目前不从持久化存储恢复；门体控制器也没有位置传感器，控制器 ack 不等价于独立门磁/锁舌实测。进程重启后的软件状态不能被当作实物状态权威值；实机应用前应增加设备状态同步或将未知状态设为 fail-closed。
- MQTT 硬件适配器当前只支持固定开门/关门动作；锁舌锁定、解锁及反锁/释放反锁只有模拟实现，硬件模式明确返回不支持。扩展这些动作前，需完成固件命令、认证、状态反馈和回执契约。
- 受控协议桥和 STM32 固件必须独立实施同一 request_id/命令指纹去重，并通过重启、重复帧、ack 丢失和过期命令实测；目前硬件固件尚未完成该验证。
- 当前 MQTT 假客户端只验证软件发布次数与回执关联；真实 Broker、ESP8266、STM32、机智云及执行器联调结果需另行记录。

## 7. 工作区说明

根目录 `.gitignore` 将整个 `financial_rag/` 排除，因此本记录引用的 Python 源码和测试修改虽然已写入本地文件并参与本地测试，但不会出现在根仓库的普通 `git status`/`git diff` 中。此次没有强行 `git add` 改变忽略策略。归档、提交或交付补丁前，需要由项目维护者确定该源码目录的版本管理方式。
