"""智能家居设备服务：状态查询、安全控制与场景预设执行。"""

from datetime import datetime, timedelta, timezone
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .adapters import DeviceAdapter, DoorActuator
from .device_models import (
    AutomationMode,
    DeviceCommand,
    DeviceCommandResult,
    DeviceRegistration,
    DeviceState,
    DeviceStateValue,
    DeviceType,
    DoorLockAction,
    DoorLockCommandResult,
    DoorLockState,
    DoorState,
    EnvironmentAlert,
    EnvironmentSnapshot,
    EnvironmentThresholds,
    HomeScenarioName,
    SensorReading,
    SceneActionResult,
    SceneExecutionResult,
    SensorRegistration,
    ThresholdName,
)
from .environment_history import EnvironmentHistoryService
from .environment_monitor import (
    DEFAULT_ENVIRONMENT_CONFIG,
    EnvironmentAlertService,
    EnvironmentMonitorConfig,
    assess_reading,
)
from .door_lock import DoorLockService
from .safety_rules import evaluate_control_risk, validate_expected_device_type
from .scene_policy import blocked_reason, tool_allowed
from .simulated_device import (
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    ExpiredCommandError,
)

DEFAULT_COMMAND_TTL_SECONDS: Final[int] = 15

class DeviceService:
    """统一封装设备适配器与安全规则。"""

    def __init__(
        self,
        adapter: DeviceAdapter,
        default_room: str = "study",
        *,
        history_service: EnvironmentHistoryService | None = None,
        alert_service: EnvironmentAlertService | None = None,
        environment_config: EnvironmentMonitorConfig | None = None,
        door_lock_service: DoorLockService | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_room = default_room
        self._environment_config = environment_config or DEFAULT_ENVIRONMENT_CONFIG
        self._history = history_service or EnvironmentHistoryService()
        self._alerts = alert_service or EnvironmentAlertService(self._environment_config)
        self._automation_mode = AutomationMode.MANUAL
        self._scene = HomeScenarioName.NORMAL
        self._door_lock = door_lock_service or DoorLockService(
            room=default_room,
            actuator=adapter if isinstance(adapter, DoorActuator) else None,
        )

    def list_devices(self) -> list[DeviceState]:
        """列出设备状态。"""

        return self._adapter.list_states()

    def get_device(self, device_id: str) -> DeviceState:
        """读取单个设备状态。"""

        return self._adapter.read_state(device_id)

    def get_automation_mode(self) -> AutomationMode:
        """读取版本三手动/自动控制模式。"""

        return self._automation_mode

    def set_automation_mode(
        self,
        mode: AutomationMode,
        *,
        source: str = "manual",
    ) -> AutomationMode:
        """切换手动或自动设备控制模式。"""

        if source == "manual" and not tool_allowed(self._scene, "set_automation_mode"):
            raise ValueError(blocked_reason(self._scene, "set_automation_mode"))
        self._automation_mode = mode
        return mode

    def get_scene(self) -> HomeScenarioName:
        """读取当前场景预设；它独立于手动/自动主控制模式。"""

        return self._scene

    def run_scenario(
        self,
        scene: HomeScenarioName,
        *,
        request_id: str | None = None,
    ) -> SceneExecutionResult:
        """执行 normal/sleep/away 固定场景，并保留逐动作结果。"""

        target = HomeScenarioName(scene)
        previous = self._scene
        base_request_id = _coerce_request_id(request_id)
        actions: list[SceneActionResult] = []

        if target is HomeScenarioName.NORMAL:
            self._scene = target
            actions.append(
                SceneActionResult(
                    name="select_normal_scene",
                    accepted=True,
                    message="Normal scene selected without changing device state",
                )
            )
        else:
            actions.extend(self._run_scene_switch_actions(target, base_request_id))
            if all(action.accepted for action in actions):
                self._scene = target

        accepted = bool(actions) and all(action.accepted for action in actions)
        if accepted:
            overall_status = "success"
        elif any(action.accepted for action in actions):
            overall_status = "partial_failed"
        else:
            overall_status = "failed"
        return SceneExecutionResult(
            room=self._default_room,
            scene=target,
            previous_scene=previous,
            accepted=accepted,
            overall_status=overall_status,
            message=(
                f"Scene {target.value} executed"
                if accepted
                else f"Scene {target.value} was not fully applied"
            ),
            actions=tuple(actions),
        )

    def _run_scene_switch_actions(
        self,
        scene: HomeScenarioName,
        base_request_id: UUID,
    ) -> list[SceneActionResult]:
        """执行场景的固定开关与门锁步骤，失败后停止后续动作。"""

        actions: list[SceneActionResult] = []
        switch_steps = {
            HomeScenarioName.SLEEP: (("desk_light", DeviceStateValue.OFF),),
            HomeScenarioName.AWAY: (
                ("desk_light", DeviceStateValue.OFF),
                ("desk_fan", DeviceStateValue.OFF),
            ),
        }[scene]
        for index, (device_id, state) in enumerate(switch_steps):
            result = self.set_switch_state(
                device_id,
                state,
                request_id=str(uuid5(base_request_id, f"{scene.value}:switch:{index}")),
                source="scene",
            )
            actions.append(
                SceneActionResult(
                    name=f"set_{device_id}_{state.value}",
                    accepted=result.accepted,
                    message=result.message,
                    device_id=device_id,
                    command_result=result,
                )
            )
            if not result.accepted:
                return actions

        lock_action = (
            DoorLockAction.ENGAGE_DEADBOLT
            if scene is HomeScenarioName.SLEEP
            else DoorLockAction.LOCK
        )
        lock_result = self.command_door_lock(
            lock_action,
            request_id=str(uuid5(base_request_id, f"{scene.value}:lock")),
        )
        actions.append(
            SceneActionResult(
                name=lock_action.value,
                accepted=lock_result.accepted,
                message=lock_result.message,
                device_id=lock_result.device_id,
                lock_result=lock_result,
            )
        )
        return actions

    def get_thresholds(self) -> EnvironmentThresholds:
        """返回当前进程内生效的版本三阈值。"""

        return EnvironmentThresholds(
            temperature_max=float(self._environment_config.temperature.danger_max),
            humidity_max=float(self._environment_config.humidity.danger_max),
            smoke_max=float(self._environment_config.smoke.danger_max),
        )

    def set_threshold(
        self,
        name: ThresholdName,
        value: float,
        *,
        source: str = "manual",
    ) -> EnvironmentThresholds:
        """校验并更新固定阈值；模拟模式在当前进程生命周期内保存。"""

        if source == "manual" and not tool_allowed(self._scene, "set_environment_threshold"):
            raise ValueError(blocked_reason(self._scene, "set_environment_threshold"))
        ranges = {
            ThresholdName.TEMPERATURE_MAX: (-20.0, 80.0),
            ThresholdName.HUMIDITY_MAX: (1.0, 100.0),
            ThresholdName.SMOKE_MAX: (1.0, 4095.0),
        }
        minimum, maximum = ranges[name]
        numeric = float(value)
        if not minimum <= numeric <= maximum:
            raise ValueError(f"threshold value outside allowed range [{minimum}, {maximum}]")
        field_name, boundary = {
            ThresholdName.TEMPERATURE_MAX: ("temperature", "danger_max"),
            ThresholdName.HUMIDITY_MAX: ("humidity", "danger_max"),
            ThresholdName.SMOKE_MAX: ("smoke", "danger_max"),
        }[name]
        metric = getattr(self._environment_config, field_name).model_copy(
            update={boundary: numeric}
        )
        self._environment_config = self._environment_config.model_copy(
            update={field_name: metric}
        )
        self._alerts = EnvironmentAlertService(self._environment_config)
        return self.get_thresholds()

    def get_door_lock(self) -> DoorLockState:
        """读取实验门锁与门磁状态。"""

        return self._door_lock.get_status()

    def set_door_state(self, door_state: DoorState) -> DoorLockState:
        """更新模拟门磁状态，供联调和测试使用。"""

        return self._door_lock.set_door_state(door_state)

    def command_door_lock(
        self,
        action: DoorLockAction,
        *,
        authorized: bool = False,
        confirmed: bool = False,
        request_id: str | None = None,
        ttl_seconds: int = 15,
    ) -> DoorLockCommandResult:
        """通过固定门锁服务执行动作并等待模拟 ack。"""

        return self._door_lock.execute(
            action,
            authorized=authorized,
            confirmed=confirmed,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
        )

    def get_environment(self, room: str | None = None) -> EnvironmentSnapshot:
        """读取环境传感器快照。"""

        target_room = room or self._default_room
        readings = tuple(
            _assessed_reading(item, self._environment_config)
            for item in self._adapter.list_sensor_readings(target_room)
        )
        snapshot = EnvironmentSnapshot(
            room=target_room,
            readings=readings,
            generated_at=datetime.now(timezone.utc),
        )
        self._history.append(snapshot)
        return snapshot

    def get_environment_history(
        self,
        room: str | None = None,
        minutes: int = 10,
    ) -> list[EnvironmentSnapshot]:
        """读取最近时间窗口内的环境历史快照。"""

        return self._history.list_snapshots(room or self._default_room, minutes=minutes)

    def evaluate_environment(self, room: str | None = None) -> list[EnvironmentAlert]:
        """评估当前房间环境，并在危险确认后联动固定风扇工具链。"""

        snapshot = self.get_environment(room)
        alerts = [
            alert
            for reading in snapshot.readings
            if (alert := self._alerts.evaluate(reading, now=snapshot.generated_at)) is not None
        ]
        if self._automation_mode is not AutomationMode.AUTOMATIC:
            return alerts
        for alert in alerts:
            if alert.state.value != "active":
                continue
            if alert.related_action in {"fan_on", "fan_and_buzzer_on"}:
                self.set_switch_state("desk_fan", DeviceStateValue.ON, source="automatic")
            if alert.related_action in {"fan_and_buzzer_on", "sprinkler_and_buzzer_on"}:
                self.set_buzzer_state(DeviceStateValue.ON, source="automatic")
            if alert.related_action == "sprinkler_and_buzzer_on":
                self.set_pump_state(DeviceStateValue.ON, source="automatic")
            if alert.related_action == "light_on":
                self.set_switch_state("desk_light", DeviceStateValue.ON, source="automatic")
        return alerts

    def set_switch_state(
        self,
        device_id: str,
        state: DeviceStateValue,
        request_id: str | None = None,
        *,
        source: str = "manual",
    ) -> DeviceCommandResult:
        """只控制灯和风扇，阻止专用执行器进入通用 on/off 通道。"""

        try:
            current = self._adapter.read_state(device_id)
        except (DeviceNotFoundError, DeviceOfflineError, ExpiredCommandError, DeviceError) as exc:
            return self._blocked_result(device_id, state, request_id, str(exc))
        if current.device_type not in {DeviceType.LIGHT, DeviceType.FAN}:
            return self._blocked_result(
                device_id,
                state,
                request_id,
                f"Device type {current.device_type.value} requires a dedicated control endpoint",
            )
        if state not in {DeviceStateValue.ON, DeviceStateValue.OFF}:
            return self._blocked_result(device_id, state, request_id, "Switch state must be on or off")
        return self.set_device_state(
            device_id,
            state,
            request_id=request_id,
            expected_device_type=current.device_type,
            source=source,
        )

    def set_pump_state(
        self,
        state: DeviceStateValue,
        request_id: str | None = None,
        *,
        source: str = "manual",
    ) -> DeviceCommandResult:
        """通过专用接口控制模拟喷淋水泵。"""

        return self._set_dedicated_switch_state(
            "sprinkler_pump", DeviceType.WATER_PUMP, state, request_id, source=source
        )

    def set_buzzer_state(
        self,
        state: DeviceStateValue,
        request_id: str | None = None,
        *,
        source: str = "manual",
    ) -> DeviceCommandResult:
        """通过专用接口控制报警蜂鸣器。"""

        return self._set_dedicated_switch_state(
            "alarm_buzzer", DeviceType.BUZZER, state, request_id, source=source
        )

    def _set_dedicated_switch_state(
        self,
        device_id: str,
        expected_device_type: DeviceType,
        state: DeviceStateValue,
        request_id: str | None,
        *,
        source: str = "manual",
    ) -> DeviceCommandResult:
        if state not in {DeviceStateValue.ON, DeviceStateValue.OFF}:
            return self._blocked_result(device_id, state, request_id, "State must be on or off")
        return self.set_device_state(
            device_id,
            state,
            request_id=request_id,
            expected_device_type=expected_device_type,
            source=source,
        )

    def _blocked_result(
        self,
        device_id: str,
        state: DeviceStateValue,
        request_id: str | None,
        reason: str,
    ) -> DeviceCommandResult:
        return DeviceCommandResult(
            request_id=_coerce_request_id(request_id),
            device_id=device_id,
            accepted=False,
            state=state,
            acknowledged_at=datetime.now(timezone.utc),
            message=reason,
            blocked_reason=reason,
        )

    def get_environment_alerts(
        self,
        room: str | None = None,
        active_only: bool = False,
    ) -> list[EnvironmentAlert]:
        """评估并返回环境报警事件。"""

        self.evaluate_environment(room)
        return self._alerts.list_alerts(room or self._default_room, active_only=active_only)

    def set_device_state(
        self,
        device_id: str,
        state: DeviceStateValue,
        request_id: str | None = None,
        ttl_seconds: int = DEFAULT_COMMAND_TTL_SECONDS,
        expected_device_type: DeviceType | None = None,
        *,
        source: str = "manual",
        tool_name: str | None = None,
    ) -> DeviceCommandResult:
        """安全控制设备开关状态。"""

        command = DeviceCommand(
            request_id=_coerce_request_id(request_id),
            device_id=device_id,
            action="set_state",
            state=state,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        decision = evaluate_control_risk(command)
        if decision.allowed:
            try:
                current_state = self._adapter.read_state(device_id)
            except (DeviceNotFoundError, DeviceOfflineError, ExpiredCommandError, DeviceError) as exc:
                return DeviceCommandResult(
                    request_id=command.request_id,
                    device_id=device_id,
                    accepted=False,
                    state=state,
                    acknowledged_at=datetime.now(timezone.utc),
                    message=str(exc),
                    blocked_reason=str(exc),
                )
            if (
                expected_device_type is None
                and current_state.device_type
                in {DeviceType.DOOR_LOCK, DeviceType.WATER_PUMP, DeviceType.BUZZER}
            ):
                return self._blocked_result(
                    device_id,
                    state,
                    command.request_id,
                    "Door locks and dedicated actuators require their dedicated control endpoints",
                )
            if expected_device_type is not None:
                decision = validate_expected_device_type(current_state, expected_device_type)
            resolved_tool_name = tool_name or _tool_name_for_device_type(current_state.device_type)
            if (
                decision.allowed
                and source == "manual"
                and resolved_tool_name is not None
                and not tool_allowed(self._scene, resolved_tool_name)
            ):
                return self._blocked_result(
                    device_id,
                    state,
                    command.request_id,
                    blocked_reason(self._scene, resolved_tool_name),
                )
        if not decision.allowed:
            return DeviceCommandResult(
                request_id=command.request_id,
                device_id=device_id,
                accepted=False,
                state=state,
                acknowledged_at=datetime.now(timezone.utc),
                message=decision.reason,
                blocked_reason=decision.reason,
            )
        try:
            return self._adapter.send_command(command)
        except (DeviceNotFoundError, DeviceOfflineError, ExpiredCommandError, DeviceError) as exc:
            return DeviceCommandResult(
                request_id=command.request_id,
                device_id=device_id,
                accepted=False,
                state=state,
                acknowledged_at=datetime.now(timezone.utc),
                message=str(exc),
                blocked_reason=str(exc),
            )

def _coerce_request_id(request_id: str | None) -> UUID:
    """将可选请求 ID 转为 UUID，缺省则生成。"""

    if not request_id:
        return uuid4()
    try:
        return UUID(str(request_id))
    except ValueError:
        return uuid5(NAMESPACE_URL, request_id)


def _tool_name_for_device_type(device_type: DeviceType) -> str | None:
    """将设备类型映射到场景策略使用的固定控制工具名。"""

    return {
        DeviceType.LIGHT: "set_light_state",
        DeviceType.FAN: "set_fan_state",
        DeviceType.WATER_PUMP: "set_sprinkler_pump_state",
        DeviceType.BUZZER: "set_alarm_buzzer_state",
    }.get(device_type)


__all__ = [
    "DeviceService",
    "DeviceRegistration",
    "SensorRegistration",
    "SensorReading",
]


def _assessed_reading(reading: SensorReading, config: EnvironmentMonitorConfig) -> SensorReading:
    """将质量与分级结果写回不可变读数快照。"""

    assessed = assess_reading(reading, config)
    return SensorReading(
        **reading.model_dump(exclude={"quality", "level"}),
        quality=assessed.quality,
        level=assessed.level,
    )
