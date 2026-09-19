"""智能家居设备服务：状态查询、安全控制与场景执行。"""

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
    HomeModeName,
    HomeScenarioName,
    ModeExecutionResult,
    ModeExecutionStatus,
    ModeStepResult,
    ScenarioExecutionResult,
    SensorReading,
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
from .simulated_device import (
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    ExpiredCommandError,
)

DEFAULT_COMMAND_TTL_SECONDS: Final[int] = 15

_SLEEP_OFF_DEVICES: Final[tuple[str, ...]] = ("desk_light", "desk_fan")
_AWAY_OFF_DEVICES: Final[tuple[str, ...]] = ("desk_light", "desk_fan")
_MOVIE_OFF_DEVICES: Final[tuple[str, ...]] = ("desk_fan",)

_SLEEP_MODE_PLAN: Final[tuple[tuple[str, str, DeviceType], ...]] = (
    ("turn_off_light", "desk_light", DeviceType.LIGHT),
)
_AWAY_MODE_PLAN: Final[tuple[tuple[str, str, DeviceType], ...]] = (
    ("turn_off_light", "desk_light", DeviceType.LIGHT),
    ("turn_off_fan", "desk_fan", DeviceType.FAN),
)


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
        self._mode = HomeModeName.NORMAL
        self._automation_mode = AutomationMode.MANUAL
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

    def get_mode(self) -> HomeModeName:
        """读取当前运行模式。"""

        return self._mode

    def get_automation_mode(self) -> AutomationMode:
        """读取版本三手动/自动控制模式。"""

        return self._automation_mode

    def set_automation_mode(self, mode: AutomationMode) -> AutomationMode:
        """切换阈值自动联动；不改变睡眠/离家场景配置。"""

        self._automation_mode = mode
        return mode

    def get_thresholds(self) -> EnvironmentThresholds:
        """返回当前进程内生效的版本三阈值。"""

        return EnvironmentThresholds(
            temperature_max=float(self._environment_config.temperature.danger_max),
            humidity_max=float(self._environment_config.humidity.danger_max),
            illuminance_min=float(self._environment_config.illuminance.danger_min),
            smoke_max=float(self._environment_config.smoke.danger_max),
        )

    def set_threshold(self, name: ThresholdName, value: float) -> EnvironmentThresholds:
        """校验并更新固定阈值；模拟模式在当前进程生命周期内保存。"""

        ranges = {
            ThresholdName.TEMPERATURE_MAX: (-20.0, 80.0),
            ThresholdName.HUMIDITY_MAX: (1.0, 100.0),
            ThresholdName.ILLUMINANCE_MIN: (0.0, 100000.0),
            ThresholdName.SMOKE_MAX: (1.0, 4095.0),
        }
        minimum, maximum = ranges[name]
        numeric = float(value)
        if not minimum <= numeric <= maximum:
            raise ValueError(f"threshold value outside allowed range [{minimum}, {maximum}]")
        field_name, boundary = {
            ThresholdName.TEMPERATURE_MAX: ("temperature", "danger_max"),
            ThresholdName.HUMIDITY_MAX: ("humidity", "danger_max"),
            ThresholdName.ILLUMINANCE_MIN: ("illuminance", "danger_min"),
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

    def set_mode(
        self,
        mode: HomeModeName,
        request_prefix: str | None = None,
    ) -> ModeExecutionResult:
        """按固定顺序执行模式切换，并如实汇总每一步结果。"""

        previous_mode = self._mode
        if mode is HomeModeName.NORMAL:
            self._mode = mode
            return ModeExecutionResult(
                mode=mode,
                previous_mode=previous_mode,
                accepted=True,
                overall_status=ModeExecutionStatus.SUCCESS,
                actions=(),
                message="Mode normal activated",
            )

        prefix = request_prefix or str(uuid4())
        actions: list[ModeStepResult] = []
        for index, (name, device_id, device_type) in enumerate(_mode_device_plan(mode)):
            result = self.set_device_state(
                device_id=device_id,
                state=DeviceStateValue.OFF,
                request_id=f"{prefix}-{index}",
                expected_device_type=device_type,
            )
            actions.append(
                ModeStepResult(
                    name=name,
                    accepted=result.accepted,
                    message=result.message,
                    device_id=device_id,
                    command_result=result,
                )
            )

        lock_action = (
            DoorLockAction.ENGAGE_DEADBOLT
            if mode is HomeModeName.SLEEP
            else DoorLockAction.LOCK
        )
        lock_result = self.command_door_lock(lock_action)
        actions.append(
            ModeStepResult(
                name="check_door_and_lock",
                accepted=lock_result.accepted,
                message=lock_result.message,
                device_id=lock_result.device_id,
                lock_result=lock_result,
            )
        )
        accepted_count = sum(action.accepted for action in actions)
        if accepted_count == len(actions):
            status = ModeExecutionStatus.SUCCESS
            accepted = True
            self._mode = mode
            message = f"Mode {mode.value} activated"
        elif accepted_count > 0:
            status = ModeExecutionStatus.PARTIAL_FAILED
            accepted = False
            message = f"Mode {mode.value} partially failed; current mode remains {previous_mode.value}"
        else:
            status = ModeExecutionStatus.FAILED
            accepted = False
            message = f"Mode {mode.value} failed; current mode remains {previous_mode.value}"
        return ModeExecutionResult(
            mode=mode,
            previous_mode=previous_mode,
            accepted=accepted,
            overall_status=status,
            actions=tuple(actions),
            message=message,
        )

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
            if alert.related_action in {"fan_on", "fan_and_window_on"}:
                self.set_switch_state("desk_fan", DeviceStateValue.ON)
            if alert.related_action == "fan_and_window_on":
                self.set_window_state(DeviceStateValue.OPEN)
            if alert.related_action == "light_on":
                self.set_switch_state("desk_light", DeviceStateValue.ON)
        return alerts

    def set_switch_state(
        self,
        device_id: str,
        state: DeviceStateValue,
        request_id: str | None = None,
    ) -> DeviceCommandResult:
        """只控制灯和风扇，阻止门锁/窗户进入通用 on/off 通道。"""

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
        )

    def set_window_state(
        self,
        state: DeviceStateValue,
        request_id: str | None = None,
    ) -> DeviceCommandResult:
        """通过固定窗户设备执行 open/closed 状态。"""

        if state not in {DeviceStateValue.OPEN, DeviceStateValue.CLOSED}:
            return self._blocked_result("window_motor", state, request_id, "Window state must be open or closed")
        return self.set_device_state(
            "window_motor",
            state,
            request_id=request_id,
            expected_device_type=DeviceType.WINDOW,
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
                and current_state.device_type in {DeviceType.DOOR_LOCK, DeviceType.WINDOW}
            ):
                return self._blocked_result(
                    device_id,
                    state,
                    command.request_id,
                    "Door locks and windows require their dedicated control endpoints",
                )
            if expected_device_type is not None:
                decision = validate_expected_device_type(current_state, expected_device_type)
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

    def run_scenario(
        self,
        scenario: HomeScenarioName,
        request_prefix: str | None = None,
    ) -> ScenarioExecutionResult:
        """执行预置场景，逐台设备安全控制。"""

        plan = _scenario_plan(scenario)
        if not plan:
            return ScenarioExecutionResult(
                scenario=scenario,
                accepted=False,
                results=(),
                message=f"Unknown scenario: {scenario}",
            )

        prefix = request_prefix or str(uuid4())
        results: list[DeviceCommandResult] = []
        for index, (device_id, state) in enumerate(plan):
            result = self.set_device_state(
                device_id=device_id,
                state=state,
                request_id=f"{prefix}-{index}",
            )
            results.append(result)

        accepted = all(item.accepted for item in results)
        failed = [item for item in results if not item.accepted]
        if accepted:
            message = f"Scenario {scenario.value} executed"
        else:
            reasons = "; ".join(item.blocked_reason or item.message for item in failed)
            message = f"Scenario {scenario.value} partially blocked: {reasons}"
        return ScenarioExecutionResult(
            scenario=scenario,
            accepted=accepted,
            results=tuple(results),
            message=message,
        )


def _coerce_request_id(request_id: str | None) -> UUID:
    """将可选请求 ID 转为 UUID，缺省则生成。"""

    if not request_id:
        return uuid4()
    try:
        return UUID(str(request_id))
    except ValueError:
        return uuid5(NAMESPACE_URL, request_id)


def _scenario_plan(scenario: HomeScenarioName) -> list[tuple[str, DeviceStateValue]]:
    """返回场景对应的设备目标状态列表。"""

    if scenario is HomeScenarioName.SLEEP:
        return [(device_id, DeviceStateValue.OFF) for device_id in _SLEEP_OFF_DEVICES]
    if scenario is HomeScenarioName.AWAY:
        return [(device_id, DeviceStateValue.OFF) for device_id in _AWAY_OFF_DEVICES]
    if scenario is HomeScenarioName.MOVIE:
        return [(device_id, DeviceStateValue.OFF) for device_id in _MOVIE_OFF_DEVICES]
    return []


def _mode_device_plan(mode: HomeModeName) -> tuple[tuple[str, str, DeviceType], ...]:
    """返回模式切换中需要执行的灯/风扇基线动作。"""

    if mode is HomeModeName.SLEEP:
        return _SLEEP_MODE_PLAN
    if mode is HomeModeName.AWAY:
        return _AWAY_MODE_PLAN
    return ()


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
