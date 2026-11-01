"""智能家居知识图谱关系提取器。"""

from typing import Any, Callable, Dict, List, Optional

from .kg_types import RelationType, RELATION_TYPE_DESCRIPTIONS


class RelationExtractor:
    VALID_RELATION_TYPES = set(RELATION_TYPE_DESCRIPTIONS)

    async def extract(self, text: str, entities: List[Dict[str, Any]], max_retries: Optional[int] = None, callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
        by_type = {item.get("type"): item.get("name") for item in entities}
        relations: list[dict[str, Any]] = []
        device = by_type.get("DEVICE")
        room = by_type.get("ROOM")
        sensor = by_type.get("SENSOR")
        scenario = by_type.get("SCENARIO")
        action = by_type.get("ACTION")
        technology = by_type.get("TECHNOLOGY")
        if device and room:
            relations.append({"source": device, "target": room, "type": RelationType.DEVICE_IN_ROOM, "confidence": 0.9})
        if sensor and room:
            relations.append({"source": sensor, "target": room, "type": RelationType.SENSOR_IN_ROOM, "confidence": 0.9})
        if device and action:
            relations.append({"source": device, "target": action, "type": RelationType.SUPPORTS_ACTION, "confidence": 0.85})
        if scenario and action:
            relations.append({"source": scenario, "target": action, "type": RelationType.TRIGGERS, "confidence": 0.8})
        if device and technology:
            relations.append({"source": device, "target": technology, "type": RelationType.CONNECTED_BY, "confidence": 0.85})
        if callback:
            callback(f"关系提取完成: {len(relations)} 个关系")
        return relations

    async def extract_batch(self, items: List[Dict[str, Any]], **kwargs: Any) -> List[List[Dict[str, Any]]]:
        return [await self.extract(item.get("text", ""), item.get("entities", []), **kwargs) for item in items]

    def _merge_relations(self, relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keys = set()
        result = []
        for relation in relations:
            key = (relation.get("source"), relation.get("target"), relation.get("type"))
            if key not in keys and relation.get("type") in self.VALID_RELATION_TYPES:
                keys.add(key)
                result.append(relation)
        return result

    async def extract_with_descriptions(self, text: str, entities: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        relations = await self.extract(text, entities, **kwargs)
        return [{**item, "description": RELATION_TYPE_DESCRIPTIONS[item["type"]]} for item in relations]


relation_extractor = RelationExtractor()
