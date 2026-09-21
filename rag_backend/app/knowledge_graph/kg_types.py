"""智能家居知识图谱的实体与关系类型。"""

from typing import Dict


class EntityType:
    DEVICE = "DEVICE"
    SENSOR = "SENSOR"
    ROOM = "ROOM"
    SCENARIO = "SCENARIO"
    SAFETY_RULE = "SAFETY_RULE"
    ACTION = "ACTION"
    STATE = "STATE"
    TECHNOLOGY = "TECHNOLOGY"
    LOCATION = "LOCATION"
    DATE_PERIOD = "DATE_PERIOD"


ENTITY_TYPE_DESCRIPTIONS: Dict[str, str] = {
    EntityType.DEVICE: "可控制的设备，如灯、风扇、门锁和插座",
    EntityType.SENSOR: "环境或状态传感器，如温度、湿度、烟雾、火焰和有人传感器",
    EntityType.ROOM: "房间或区域，如书房、客厅和卧室",
    EntityType.SCENARIO: "兼容的规则集合；版本三实际使用手动/自动控制模式",
    EntityType.SAFETY_RULE: "设备控制安全规则和限制",
    EntityType.ACTION: "设备动作，如打开、关闭和读取状态",
    EntityType.STATE: "设备状态或传感器读数",
    EntityType.TECHNOLOGY: "通信或集成技术，如 MQTT、ESP8266 和机智云",
    EntityType.LOCATION: "家庭位置或区域",
    EntityType.DATE_PERIOD: "时间或时间段",
}


class RelationType:
    DEVICE_IN_ROOM = "DEVICE_IN_ROOM"
    SENSOR_IN_ROOM = "SENSOR_IN_ROOM"
    SUPPORTS_ACTION = "SUPPORTS_ACTION"
    TRIGGERS = "TRIGGERS"
    REQUIRES_SAFETY = "REQUIRES_SAFETY"
    REPORTS_STATE = "REPORTS_STATE"
    CONNECTED_BY = "CONNECTED_BY"
    RELATED_TO = "RELATED_TO"


RELATION_TYPE_DESCRIPTIONS: Dict[str, str] = {
    RelationType.DEVICE_IN_ROOM: "设备位于房间",
    RelationType.SENSOR_IN_ROOM: "传感器位于房间",
    RelationType.SUPPORTS_ACTION: "设备支持动作",
    RelationType.TRIGGERS: "传感器或条件触发场景/动作",
    RelationType.REQUIRES_SAFETY: "动作需要安全规则",
    RelationType.REPORTS_STATE: "设备或传感器上报状态",
    RelationType.CONNECTED_BY: "设备通过通信技术连接",
    RelationType.RELATED_TO: "通用关联",
}


def get_entity_type_prompt_block() -> str:
    return "\n".join(["实体类型："] + [f"- {key}: {value}" for key, value in ENTITY_TYPE_DESCRIPTIONS.items()])


def get_relation_type_prompt_block() -> str:
    return "\n".join(["关系类型："] + [f"- {key}: {value}" for key, value in RELATION_TYPE_DESCRIPTIONS.items()])
