"""智能家居知识图谱实体提取器。"""

import re
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings
from .kg_types import EntityType, ENTITY_TYPE_DESCRIPTIONS


class EntityExtractor:
    VALID_ENTITY_TYPES = set(ENTITY_TYPE_DESCRIPTIONS)

    def __init__(self) -> None:
        self.confidence_threshold = getattr(settings, "ENTITY_CONFIDENCE_THRESHOLD", 0.7)

    async def extract(self, text: str, resolve_coreference: bool = True, max_retries: Optional[int] = None, callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
        entities = self._pre_extract_by_rules(text)
        if callback:
            callback(f"实体提取完成: {len(entities)} 个实体")
        return self._merge_entities(entities)

    async def extract_batch(self, texts: List[str], **kwargs: Any) -> List[List[Dict[str, Any]]]:
        return [await self.extract(text, **kwargs) for text in texts]

    def _pre_extract_by_rules(self, text: str) -> List[Dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        patterns = {
            EntityType.DEVICE: r"(?:desk_light|desk_fan|sprinkler_pump|alarm_buzzer|灯|风扇|水泵|蜂鸣器|门锁)",
            EntityType.SENSOR: r"(?:温度|湿度|烟雾|火焰|有人|人体|传感器)",
            EntityType.ROOM: r"(?:书房|客厅|卧室|厨房|卫生间|study|living_room|bedroom)",
            EntityType.SCENARIO: r"(?:手动模式|自动模式|manual|automatic)",
            EntityType.ACTION: r"(?:打开|关闭|开启|关掉|读取|查询|控制|on|off)",
            EntityType.TECHNOLOGY: r"(?:MQTT|ESP8266|Wi-Fi|机智云|蓝牙)",
        }
        for entity_type, pattern in patterns.items():
            for value in dict.fromkeys(re.findall(pattern, text, flags=re.IGNORECASE)):
                entities.append({"name": value, "type": entity_type, "confidence": 0.95})
        return entities

    def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for entity in entities:
            key = (str(entity.get("name", "")).strip(), str(entity.get("type", "")))
            if key[0] and key[1] in self.VALID_ENTITY_TYPES:
                merged.setdefault(key, dict(entity))
                merged[key]["confidence"] = max(merged[key].get("confidence", 0.0), entity.get("confidence", 0.0))
        return list(merged.values())

    async def extract_with_descriptions(self, text: str, **kwargs: Any) -> List[Dict[str, Any]]:
        entities = await self.extract(text, **kwargs)
        return [{**item, "description": ENTITY_TYPE_DESCRIPTIONS.get(item["type"], "智能家居实体")} for item in entities]


entity_extractor = EntityExtractor()
