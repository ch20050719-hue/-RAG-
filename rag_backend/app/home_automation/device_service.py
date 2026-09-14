"""智能家居设备服务：状态查询、安全控制与场景执行。"""

from datetime import datetime, timedelta, timezone
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .adapters import DeviceAdapter
from .device_models import (
    DeviceCommand,
    DeviceCommandResult,
    DeviceRegistration,
    DeviceState,
    DeviceStateValue,
    DeviceType,
    EnvironmentSnapshot,
    HomeScenarioName,
    ScenarioExecutionResult,
    SensorReading,
    SensorRegistration,
)
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


class DeviceService:
    """统一封装设备适配器与安全规则。"""

    def __init__(self, adapter: DeviceAdapter, default_room: str = "study") -> None:
        self._adapter = adapter
        self._default_room = default_room

    def list_devices(self) -> list[DeviceState]:
        """列出设备状态。"""

        return self._adapter.list_states()

    def get_device(self, device_id: str) -> DeviceState:
        """读取单个设备状态。"""

        return self._adapter.read_state(device_id)

    def get_environment(self, room: str | None = None) -> EnvironmentSnapshot:
        """读取环境传感器快照。"""

        target_room = room or self._default_room
        readings = self._adapter.list_sensor_readings(target_room)
        return EnvironmentSnapshot(
            room=target_room,
            readings=tuple(readings),
            generated_at=datetime.now(timezone.utc),
        )

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
        if decision.allowed and expected_device_type is not None:
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


__all__ = [
    "DeviceService",
    "DeviceRegistration",
    "SensorRegistration",
    "SensorReading",
]
