"""实验门锁的固定动作、门磁安全校验与模拟 ack。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .adapters import DoorActuator
from .device_models import (
    BatteryState,
    DoorActuatorResult,
    DeadboltState,
    DoorLockAckStatus,
    DoorLockAction,
    DoorLockCommandResult,
    DoorLockState,
    DoorState,
    LockState,
)

DEFAULT_DOOR_LOCK_ID: Final[str] = "door_lock"
DEFAULT_DOOR_LOCK_ROOM: Final[str] = "study"
DEFAULT_DOOR_LOCK_COMMAND_TTL_SECONDS: Final[int] = 15


class DoorLockService:
    """提供单个实验门锁的安全控制闭环。"""

    def __init__(
        self,
        device_id: str = DEFAULT_DOOR_LOCK_ID,
        room: str = DEFAULT_DOOR_LOCK_ROOM,
        *,
        online: bool = True,
        battery_level: int = 100,
        door_state: DoorState = DoorState.CLOSED,
        actuator: DoorActuator | None = None,
    ) -> None:
        self._state = DoorLockState(
            device_id=device_id,
            room=room,
            door_state=door_state,
            lock_state=LockState.UNLOCKED,
            latch_state=LockState.UNLOCKED,
            deadbolt_state=DeadboltState.RELEASED,
            online=online,
            battery_state=BatteryState.LOW if battery_level < 20 else BatteryState.NORMAL,
            battery_level=battery_level,
            ack_status=DoorLockAckStatus.SUCCESS,
            updated_at=datetime.now(timezone.utc),
        )
        self._results: dict[str, DoorLockCommandResult] = {}
        self._logs: tuple[DoorLockCommandResult, ...] = ()
        self._actuator = actuator

    def get_status(self) -> DoorLockState:
        """读取门锁和门磁状态。"""

        return self._state

    def set_door_state(self, door_state: DoorState) -> DoorLockState:
        """更新模拟门磁状态，仅供硬件模拟与测试使用。"""

        now = datetime.now(timezone.utc)
        self._state = DoorLockState(
            **self._state.model_dump(exclude={"door_state", "updated_at"}),
            door_state=door_state,
            updated_at=now,
        )
        return self._state

    def set_online(self, online: bool) -> DoorLockState:
        """更新模拟门锁在线状态。"""

        now = datetime.now(timezone.utc)
        self._state = DoorLockState(
            **self._state.model_dump(exclude={"online", "updated_at"}),
            online=online,
            updated_at=now,
        )
        return self._state

    def set_jammed(self, jammed: bool) -> DoorLockState:
        """更新模拟门锁卡滞状态。"""

        now = datetime.now(timezone.utc)
        self._state = DoorLockState(
            **self._state.model_dump(exclude={"jammed", "updated_at"}),
            jammed=jammed,
            updated_at=now,
        )
        return self._state

    def execute(
        self,
        action: DoorLockAction,
        *,
        authorized: bool = False,
        confirmed: bool = False,
        request_id: str | None = None,
        ttl_seconds: int = DEFAULT_DOOR_LOCK_COMMAND_TTL_SECONDS,
    ) -> DoorLockCommandResult:
        """执行固定门锁动作并返回成功或失败 ack。"""

        command = DoorLockAction(action)
        request_uuid = _coerce_request_id(request_id)
        request_key = str(request_uuid)
        if request_key in self._results:
            return self._results[request_key]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        reason = self._failure_reason(command, authorized, confirmed, expires_at, now)
        if reason is not None:
            result = self._finish(
                request_uuid,
                command,
                accepted=False,
                ack_status=DoorLockAckStatus.FAILED,
                message=reason,
                blocked_reason=reason,
                now=now,
                expires_at=expires_at,
            )
            return result

        door_state = self._state.door_state
        if command in (DoorLockAction.OPEN_DOOR, DoorLockAction.CLOSE_DOOR):
            actuator_result = self._execute_door_motion(command, request_uuid, expires_at)
            if not actuator_result.accepted:
                return self._finish(
                    request_uuid,
                    command,
                    accepted=False,
                    ack_status=actuator_result.ack_status,
                    message=actuator_result.message,
                    blocked_reason=actuator_result.blocked_reason or actuator_result.message,
                    now=now,
                    expires_at=expires_at,
                )
            door_state = (
                DoorState.OPEN
                if command is DoorLockAction.OPEN_DOOR
                else DoorState.CLOSED
            )

        if command is DoorLockAction.UNLOCK:
            latch_state = LockState.UNLOCKED
            deadbolt_state = self._state.deadbolt_state
        elif command is DoorLockAction.LOCK:
            latch_state = LockState.LOCKED
            deadbolt_state = self._state.deadbolt_state
        elif command is DoorLockAction.ENGAGE_DEADBOLT:
            latch_state = self._effective_latch_state()
            deadbolt_state = DeadboltState.ENGAGED
        elif command in (DoorLockAction.OPEN_DOOR, DoorLockAction.CLOSE_DOOR):
            latch_state = self._effective_latch_state()
            deadbolt_state = self._state.deadbolt_state
        else:
            latch_state = self._effective_latch_state()
            deadbolt_state = DeadboltState.RELEASED

        updated = DoorLockState(
            **self._state.model_dump(
                exclude={
                    "door_state",
                    "lock_state",
                    "latch_state",
                    "deadbolt_state",
                    "last_command",
                    "ack_status",
                    "updated_at",
                }
            ),
            door_state=door_state,
            lock_state=latch_state,
            latch_state=latch_state,
            deadbolt_state=deadbolt_state,
            last_command=command.value,
            ack_status=DoorLockAckStatus.SUCCESS,
            updated_at=now,
        )
        self._state = updated
        result = self._result(
            request_uuid,
            command,
            accepted=True,
            ack_status=DoorLockAckStatus.SUCCESS,
            message=f"Door lock command {command.value} acknowledged",
            blocked_reason=None,
            now=now,
            state=updated,
            expires_at=expires_at,
        )
        self._results[request_key] = result
        self._logs = (*self._logs, result)
        return result

    def list_logs(self) -> list[DoorLockCommandResult]:
        """返回门锁命令日志。"""

        return list(self._logs)

    def _failure_reason(
        self,
        action: DoorLockAction,
        authorized: bool,
        confirmed: bool,
        expires_at: datetime,
        now: datetime,
    ) -> str | None:
        if action in (
            DoorLockAction.UNLOCK,
            DoorLockAction.RELEASE_DEADBOLT,
            DoorLockAction.OPEN_DOOR,
            DoorLockAction.CLOSE_DOOR,
        ) and not authorized:
            return "User authorization is required for this door lock action"
        if action is DoorLockAction.RELEASE_DEADBOLT and not confirmed:
            return "Second confirmation is required to release the deadbolt"
        if expires_at <= now:
            return "Door lock command expired"
        if not self._state.online:
            return "Door lock is offline"
        if self._state.jammed:
            return "Door lock is jammed"
        if action in (DoorLockAction.LOCK, DoorLockAction.ENGAGE_DEADBOLT):
            if self._state.door_state is DoorState.OPEN:
                return "Door is open; lock action is blocked"
        if action is DoorLockAction.OPEN_DOOR:
            if self._state.latch_state is LockState.LOCKED or self._state.deadbolt_state is DeadboltState.ENGAGED:
                return "Unlock door before opening"
        if action is DoorLockAction.CLOSE_DOOR:
            if self._state.latch_state is LockState.LOCKED or self._state.deadbolt_state is DeadboltState.ENGAGED:
                return "Release the lock before closing the door"
        return None

    def _execute_door_motion(
        self,
        action: DoorLockAction,
        request_id: UUID,
        expires_at: datetime,
    ) -> DoorActuatorResult:
        if self._actuator is None:
            return DoorActuatorResult(
                request_id=request_id,
                device_id=self._state.device_id,
                action=action,
                accepted=True,
                ack_status=DoorLockAckStatus.SUCCESS,
                message=f"Simulated servo acknowledged {action.value}",
            )
        try:
            return self._actuator.execute_door_motion(
                self._state.device_id,
                action,
                request_id=request_id,
                expires_at=expires_at,
            )
        except Exception as exc:  # noqa: BLE001 - actuator boundary
            return DoorActuatorResult(
                request_id=request_id,
                device_id=self._state.device_id,
                action=action,
                accepted=False,
                ack_status=DoorLockAckStatus.FAILED,
                message=f"Door actuator failed: {exc}",
                blocked_reason=str(exc),
            )

    def _effective_latch_state(self) -> LockState:
        return self._state.latch_state or self._state.lock_state

    def _finish(
        self,
        request_id: UUID,
        action: DoorLockAction,
        *,
        accepted: bool,
        ack_status: DoorLockAckStatus,
        message: str,
        blocked_reason: str,
        now: datetime,
        expires_at: datetime,
    ) -> DoorLockCommandResult:
        self._state = DoorLockState(
            **self._state.model_dump(exclude={"last_command", "ack_status", "updated_at"}),
            last_command=action.value,
            ack_status=ack_status,
            updated_at=now,
        )
        result = self._result(
            request_id,
            action,
            accepted=accepted,
            ack_status=ack_status,
            message=message,
            blocked_reason=blocked_reason,
            now=now,
            state=self._state,
            expires_at=expires_at,
        )
        self._results[str(request_id)] = result
        self._logs = (*self._logs, result)
        return result

    def _result(
        self,
        request_id: UUID,
        action: DoorLockAction,
        *,
        accepted: bool,
        ack_status: DoorLockAckStatus,
        message: str,
        blocked_reason: str | None,
        now: datetime,
        state: DoorLockState,
        expires_at: datetime,
    ) -> DoorLockCommandResult:
        return DoorLockCommandResult(
            request_id=request_id,
            device_id=state.device_id,
            room=state.room,
            action=action,
            accepted=accepted,
            ack_status=ack_status,
            message=message,
            blocked_reason=blocked_reason,
            door_state=state.door_state,
            latch_state=state.latch_state or state.lock_state,
            deadbolt_state=state.deadbolt_state,
            battery_level=state.battery_level,
            expires_at=expires_at,
            acknowledged_at=now,
        )


def _coerce_request_id(request_id: str | None) -> UUID:
    if not request_id:
        return uuid4()
    try:
        return UUID(str(request_id))
    except ValueError:
        return uuid5(NAMESPACE_URL, str(request_id))


__all__ = ["DoorLockService"]
