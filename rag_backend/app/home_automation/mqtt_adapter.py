"""MQTT 设备适配器：与模拟适配器共用命令/回执契约。"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from .default_devices import SENSOR_UNITS
from .device_models import (
    DoorActuatorResult,
    DeviceCommand,
    DeviceCommandResult,
    DeviceRegistration,
    DeviceState,
    DeviceStateValue,
    DeviceType,
    DoorLockAckStatus,
    DoorLockAction,
    SensorQuality,
    SensorReading,
    SensorRegistration,
)
from .simulated_device import (
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    ExpiredCommandError,
)

logger = logging.getLogger(__name__)

try:  # pragma: no cover - depends on environment
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except ImportError:  # pragma: no cover
    mqtt = None
    PAHO_AVAILABLE = False


TOPIC_PREFIX: Final[str] = "home/v1"
DEFAULT_ACK_TIMEOUT_SECONDS: Final[float] = 5.0


def topic_for_state_set(room: str, device_id: str) -> str:
    """控制命令下发 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/state/set"


def topic_for_state_ack(room: str, device_id: str) -> str:
    """设备执行回执 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/state/ack"


def topic_for_telemetry(room: str, device_id: str) -> str:
    """传感器/设备遥测 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/telemetry"


def topic_for_availability(room: str, device_id: str) -> str:
    """在线状态 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/availability"


def topic_for_door_set(room: str, device_id: str) -> str:
    """门体舵机动作下发 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/door/set"


def topic_for_door_ack(room: str, device_id: str) -> str:
    """门体舵机动作回执 Topic。"""

    return f"{TOPIC_PREFIX}/{room}/{device_id}/door/ack"


def topic_for_room_availability(room: str) -> str:
    """节点级在线状态 Topic，用于 MQTT Last Will。"""

    return f"{TOPIC_PREFIX}/{room}/availability"


class MqttTransportError(DeviceError):
    """MQTT 传输层错误。"""


class MqttAckTimeoutError(DeviceError):
    """等待设备回执超时。"""


class MqttDeviceAdapter:
    """基于 MQTT 的设备适配器。未配置 paho 时仅允许构造与契约校验。"""

    def __init__(
        self,
        registrations: list[DeviceRegistration],
        sensor_registrations: list[SensorRegistration] | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        ack_timeout: float = DEFAULT_ACK_TIMEOUT_SECONDS,
        client_id: str = "home-backend",
    ) -> None:
        if not PAHO_AVAILABLE:
            raise MqttTransportError(
                "paho-mqtt is not installed. Install paho-mqtt or use SimulatedDeviceAdapter."
            )
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ack_timeout = ack_timeout
        self._client_id = client_id
        self._states: dict[str, DeviceState] = {}
        self._results: dict[str, DeviceCommandResult] = {}
        self._door_results: dict[str, DoorActuatorResult] = {}
        self._sensors: dict[str, SensorReading] = {}
        self._pending_acks: dict[str, threading.Event] = {}
        self._pending_ack_targets: dict[str, tuple[str, str]] = {}
        self._ack_payloads: dict[str, DeviceCommandResult] = {}
        self._pending_door_acks: dict[str, threading.Event] = {}
        self._pending_door_ack_targets: dict[str, tuple[str, str, DoorLockAction]] = {}
        self._door_ack_payloads: dict[str, DoorActuatorResult] = {}
        self._client: Any = None
        self._connected = False
        self._lock = threading.RLock()

        now = datetime.now(timezone.utc)
        for registration in registrations:
            self._states[registration.device_id] = DeviceState(
                device_id=registration.device_id,
                room=registration.room,
                device_type=registration.device_type,
                online=registration.online,
                updated_at=now,
            )
        for sensor in sensor_registrations or []:
            self._sensors[sensor.sensor_id] = SensorReading(
                sensor_id=sensor.sensor_id,
                room=sensor.room,
                kind=sensor.kind,
                value=0.0,
                unit=SENSOR_UNITS[sensor.kind],
                online=sensor.online,
                recorded_at=now,
                source="mqtt",
                quality=SensorQuality.VALID,
            )

    @property
    def connected(self) -> bool:
        """是否已连接 Broker。"""

        return self._connected

    def connect(self) -> None:
        """建立 MQTT 连接并订阅回执/遥测/在线状态。"""

        self._client = mqtt.Client(client_id=self._client_id, clean_session=True)
        if self._username:
            self._client.username_pw_set(self._username, self._password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        try:
            return_code = self._client.connect(self._host, self._port, keepalive=30)
        except OSError as exc:
            raise MqttTransportError(f"MQTT connect failed: {exc}") from exc
        if return_code != 0:
            raise MqttTransportError(f"MQTT connect failed with return code {return_code}")
        self._client.loop_start()
        self._connected = True

    def disconnect(self) -> None:
        """断开连接。"""

        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False

    def read_state(self, device_id: str) -> DeviceState:
        """读取本地缓存的设备状态。"""

        with self._lock:
            try:
                return self._states[device_id]
            except KeyError as exc:
                raise DeviceNotFoundError(f"Device is not registered: {device_id}") from exc

    def list_states(self) -> list[DeviceState]:
        """列出设备状态。"""

        with self._lock:
            return list(self._states.values())

    def list_sensor_readings(self, room: str | None = None) -> list[SensorReading]:
        """列出传感器读数。"""

        with self._lock:
            readings = list(self._sensors.values())
        if room is None:
            return readings
        return [item for item in readings if item.room == room]

    def send_command(self, command: DeviceCommand) -> DeviceCommandResult:
        """发布控制命令并等待设备回执。"""

        request_key = str(command.request_id)
        with self._lock:
            if request_key in self._results:
                return self._results[request_key]
            current = self._states.get(command.device_id)
            if current is None:
                raise DeviceNotFoundError(f"Device is not registered: {command.device_id}")
            if not current.online:
                raise DeviceOfflineError(f"Device is offline: {command.device_id}")
            if command.expires_at is not None and command.expires_at <= datetime.now(timezone.utc):
                raise ExpiredCommandError(f"Command has expired: {command.request_id}")
            if not self._connected or self._client is None:
                raise MqttTransportError("MQTT client is not connected")

            event = threading.Event()
            self._pending_acks[request_key] = event
            self._pending_ack_targets[request_key] = (current.room, command.device_id)

        payload = {
            "request_id": request_key,
            "action": command.action,
            "state": command.state.value,
            "expires_at": command.expires_at.isoformat() if command.expires_at else None,
        }
        topic = topic_for_state_set(current.room, command.device_id)
        try:
            publish_info = self._client.publish(topic, json.dumps(payload), qos=1)
            publish_rc = getattr(publish_info, "rc", 0)
            if publish_rc != 0:
                raise MqttTransportError(f"MQTT publish failed with return code {publish_rc}")
            wait_for_publish = getattr(publish_info, "wait_for_publish", None)
            if wait_for_publish is not None:
                wait_for_publish(timeout=self._ack_timeout)
        except Exception as exc:  # noqa: BLE001 - transport boundary
            with self._lock:
                self._pending_acks.pop(request_key, None)
                self._pending_ack_targets.pop(request_key, None)
            if isinstance(exc, MqttTransportError):
                raise
            raise MqttTransportError(f"MQTT publish failed: {exc}") from exc

        if not event.wait(timeout=self._ack_timeout):
            with self._lock:
                self._pending_acks.pop(request_key, None)
                self._pending_ack_targets.pop(request_key, None)
            raise MqttAckTimeoutError(
                f"No ack for request {request_key} within {self._ack_timeout}s"
            )

        with self._lock:
            result = self._ack_payloads.pop(request_key, None)
            self._pending_acks.pop(request_key, None)
            self._pending_ack_targets.pop(request_key, None)
            if result is None:
                raise MqttAckTimeoutError(f"Empty ack payload for request {request_key}")
            self._results[request_key] = result
            return result

    def execute_door_motion(
        self,
        device_id: str,
        action: DoorLockAction,
        *,
        request_id: UUID,
        expires_at: datetime | None,
    ) -> DoorActuatorResult:
        """发布固定舵机动作并等待 STM32 或通信模块的 door/ack。"""

        command = DoorLockAction(action)
        if command not in (DoorLockAction.OPEN_DOOR, DoorLockAction.CLOSE_DOOR):
            raise ValueError(f"Unsupported door action: {command}")
        request_key = str(request_id)
        with self._lock:
            if request_key in self._door_results:
                return self._door_results[request_key]
            current = self._states.get(device_id)
            if current is None:
                raise DeviceNotFoundError(f"Device is not registered: {device_id}")
            if current.device_type is not DeviceType.DOOR_LOCK:
                raise ValueError(f"Device is not a door lock: {device_id}")
            if not current.online:
                raise DeviceOfflineError(f"Device is offline: {device_id}")
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                raise ExpiredCommandError(f"Command has expired: {request_id}")
            if not self._connected or self._client is None:
                raise MqttTransportError("MQTT client is not connected")
            event = threading.Event()
            self._pending_door_acks[request_key] = event
            self._pending_door_ack_targets[request_key] = (current.room, device_id, command)

        payload = {
            "request_id": request_key,
            "action": command.value,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        topic = topic_for_door_set(current.room, device_id)
        try:
            publish_info = self._client.publish(topic, json.dumps(payload), qos=1)
            publish_rc = getattr(publish_info, "rc", 0)
            if publish_rc != 0:
                raise MqttTransportError(f"MQTT publish failed with return code {publish_rc}")
            wait_for_publish = getattr(publish_info, "wait_for_publish", None)
            if wait_for_publish is not None:
                wait_for_publish(timeout=self._ack_timeout)
        except Exception as exc:  # noqa: BLE001 - transport boundary
            with self._lock:
                self._pending_door_acks.pop(request_key, None)
                self._pending_door_ack_targets.pop(request_key, None)
            if isinstance(exc, MqttTransportError):
                raise
            raise MqttTransportError(f"MQTT publish failed: {exc}") from exc

        if not event.wait(timeout=self._ack_timeout):
            with self._lock:
                self._pending_door_acks.pop(request_key, None)
                self._pending_door_ack_targets.pop(request_key, None)
            raise MqttAckTimeoutError(
                f"No door ack for request {request_key} within {self._ack_timeout}s"
            )

        with self._lock:
            result = self._door_ack_payloads.pop(request_key, None)
            self._pending_door_acks.pop(request_key, None)
            self._pending_door_ack_targets.pop(request_key, None)
            if result is None:
                raise MqttAckTimeoutError(f"Empty door ack payload for request {request_key}")
            self._door_results[request_key] = result
            return result

    def ingest_telemetry(self, room: str, device_id: str, payload: dict[str, Any]) -> None:
        """处理设备/传感器遥测消息。"""

        with self._lock:
            if device_id in self._states and "state" in payload:
                state_value = DeviceStateValue(payload["state"])
                current = self._states[device_id]
                self._states[device_id] = DeviceState(
                    **current.model_dump(exclude={"state", "updated_at"}),
                    state=state_value,
                    updated_at=datetime.now(timezone.utc),
                )
            for sensor_id, value in payload.get("sensors", {}).items():
                if sensor_id not in self._sensors:
                    continue
                current = self._sensors[sensor_id]
                kind = current.kind
                self._sensors[sensor_id] = SensorReading(
                    **current.model_dump(
                        exclude={"value", "unit", "recorded_at", "source", "quality"}
                    ),
                    value=float(value),
                    unit=SENSOR_UNITS.get(kind, current.unit),
                    recorded_at=datetime.now(timezone.utc),
                    source="mqtt",
                    quality=SensorQuality.VALID,
                )

    def ingest_availability(self, room: str, device_id: str | None, online: bool) -> None:
        """更新设备在线状态。"""

        with self._lock:
            if device_id is None:
                for current_id, current in tuple(self._states.items()):
                    if current.room != room:
                        continue
                    self._states[current_id] = DeviceState(
                        **current.model_dump(exclude={"online", "updated_at"}),
                        online=online,
                        updated_at=datetime.now(timezone.utc),
                    )
                return
            if device_id not in self._states:
                return
            current = self._states[device_id]
            self._states[device_id] = DeviceState(
                **current.model_dump(exclude={"online", "updated_at"}),
                online=online,
                updated_at=datetime.now(timezone.utc),
            )

    def ingest_ack(self, room: str, device_id: str, payload: dict[str, Any]) -> None:
        """处理设备执行回执。"""

        request_id = str(payload.get("request_id", ""))
        with self._lock:
            target = self._pending_ack_targets.get(request_id)
            if target != (room, device_id):
                logger.warning(
                    "Ignoring MQTT ack for unexpected target: request_id=%s room=%s device_id=%s",
                    request_id,
                    room,
                    device_id,
                )
                return
            try:
                result = DeviceCommandResult(
                    request_id=UUID(request_id),
                    device_id=device_id,
                    accepted=bool(payload.get("accepted", False)),
                    state=DeviceStateValue(payload.get("state", "off")),
                    acknowledged_at=datetime.now(timezone.utc),
                    message=str(payload.get("message", "ack")),
                    blocked_reason=payload.get("blocked_reason"),
                )
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid MQTT ack payload: request_id=%s error=%s", request_id, exc)
                return
            self._ack_payloads[request_id] = result
            event = self._pending_acks.get(request_id)
            if result.accepted and device_id in self._states:
                current = self._states[device_id]
                self._states[device_id] = DeviceState(
                    **current.model_dump(exclude={"state", "updated_at", "last_request_id"}),
                    state=result.state,
                    updated_at=datetime.now(timezone.utc),
                    last_request_id=result.request_id,
                )
        if event is not None:
            event.set()

    def ingest_door_ack(self, room: str, device_id: str, payload: dict[str, Any]) -> None:
        """处理 STM32 或通信模块的舵机门体动作回执。"""

        request_key = str(payload.get("request_id", ""))
        with self._lock:
            target = self._pending_door_ack_targets.get(request_key)
            try:
                request_id = UUID(request_key)
                action = DoorLockAction(payload.get("action", ""))
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid door ack payload: request_id=%s error=%s", request_key, exc)
                return
            if target != (room, device_id, action):
                logger.warning(
                    "Ignoring door ack for unexpected target: request_id=%s room=%s device_id=%s action=%s",
                    request_key,
                    room,
                    device_id,
                    action.value,
                )
                return
            accepted = bool(payload.get("accepted", False))
            try:
                result = DoorActuatorResult(
                    request_id=request_id,
                    device_id=device_id,
                    action=action,
                    accepted=accepted,
                    ack_status=DoorLockAckStatus(
                        payload.get("ack_status", "success" if accepted else "failed")
                    ),
                    message=str(payload.get("message", "ack")),
                    blocked_reason=payload.get("blocked_reason"),
                )
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid door ack payload: request_id=%s error=%s", request_key, exc)
                return
            self._door_ack_payloads[request_key] = result
            event = self._pending_door_acks.get(request_key)
        if event is not None:
            event.set()

    def _on_connect(self, client, userdata, flags, rc):  # noqa: ANN001
        """连接成功后订阅全部回执与遥测。"""

        if rc != 0:
            logger.error("MQTT connect failed with code %s", rc)
            self._connected = False
            return
        for state in self.list_states():
            client.subscribe(topic_for_state_ack(state.room, state.device_id))
            client.subscribe(topic_for_telemetry(state.room, state.device_id))
            client.subscribe(topic_for_availability(state.room, state.device_id))
            if state.device_type is DeviceType.DOOR_LOCK:
                client.subscribe(topic_for_door_ack(state.room, state.device_id))
            client.subscribe(topic_for_room_availability(state.room))
        logger.info("MQTT adapter connected and subscribed")

    def _on_message(self, client, userdata, msg):  # noqa: ANN001
        """分发 Broker 消息。"""

        try:
            parts = msg.topic.split("/")
            # home/v1/{room}/{device}/{channel}
            if len(parts) == 4 and parts[3] == "availability":
                room = parts[2]
                payload = json.loads(msg.payload.decode("utf-8") or "{}")
                self.ingest_availability(room, None, bool(payload.get("online", False)))
                return
            if len(parts) < 5:
                return
            room, device_id, channel = parts[2], parts[3], parts[4]
            payload = json.loads(msg.payload.decode("utf-8") or "{}")
            if len(parts) >= 6 and channel == "door" and parts[5] == "ack":
                self.ingest_door_ack(room, device_id, payload)
            elif channel == "ack":
                self.ingest_ack(room, device_id, payload)
            elif channel == "telemetry":
                self.ingest_telemetry(room, device_id, payload)
            elif channel == "availability":
                self.ingest_availability(room, device_id, bool(payload.get("online", False)))
        except Exception:  # noqa: BLE001 - never crash MQTT loop
            logger.exception("Failed to handle MQTT message: %s", msg.topic)


__all__ = [
    "MqttDeviceAdapter",
    "MqttTransportError",
    "MqttAckTimeoutError",
    "PAHO_AVAILABLE",
    "topic_for_state_set",
    "topic_for_state_ack",
    "topic_for_telemetry",
    "topic_for_availability",
    "topic_for_door_set",
    "topic_for_door_ack",
    "topic_for_room_availability",
    "TOPIC_PREFIX",
]
