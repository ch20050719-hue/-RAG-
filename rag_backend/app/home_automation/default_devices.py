"""桌面原型默认设备与传感器注册表。"""

from typing import Final

from .device_models import DeviceRegistration, DeviceType, SensorKind, SensorRegistration

DESKTOP_ROOM: Final[str] = "study"

DEFAULT_DEVICE_REGISTRATIONS: Final[tuple[DeviceRegistration, ...]] = (
    DeviceRegistration(device_id="desk_light", room=DESKTOP_ROOM, device_type=DeviceType.LIGHT),
    DeviceRegistration(device_id="desk_fan", room=DESKTOP_ROOM, device_type=DeviceType.FAN),
    DeviceRegistration(device_id="door_lock", room=DESKTOP_ROOM, device_type=DeviceType.DOOR_LOCK),
)

DEFAULT_SENSOR_REGISTRATIONS: Final[tuple[SensorRegistration, ...]] = (
    SensorRegistration(sensor_id="room_temp", room=DESKTOP_ROOM, kind=SensorKind.TEMPERATURE),
    SensorRegistration(sensor_id="room_humidity", room=DESKTOP_ROOM, kind=SensorKind.HUMIDITY),
    SensorRegistration(sensor_id="room_co2", room=DESKTOP_ROOM, kind=SensorKind.CO2),
)

SENSOR_UNITS: Final[dict[SensorKind, str]] = {
    SensorKind.TEMPERATURE: "celsius",
    SensorKind.HUMIDITY: "percent",
    SensorKind.CO2: "ppm",
    SensorKind.ILLUMINANCE: "lux",
    SensorKind.MOTION: "bool",
}
