"""智能家居查询解析器。

保留统一检索器需要的 ``analyze`` 与过滤器接口，但只识别设备、环境、
场景和安全条件，不再暴露旧业务领域路由。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """零 LLM 依赖的智能家居查询解析器。"""

    DOMAIN_KEYWORDS = {
        "smart_home": (
            "智能家居", "智能家庭", "设备", "灯", "风扇", "空调", "传感器",
            "温度", "湿度", "光照", "人体", "环境", "mqtt", "esp32",
            "场景", "睡眠模式", "离家模式", "节能模式", "安全规则",
        ),
    }
    DEVICE_PATTERNS = {
        "desk_light": ("desk_light", "书桌灯", "台灯"),
        "desk_fan": ("desk_fan", "书桌风扇", "风扇"),
    }
    DEVICE_TYPES = {
        "灯": "light", "台灯": "light", "light": "light",
        "风扇": "fan", "fan": "fan", "空调": "air_conditioner",
        "传感器": "sensor", "sensor": "sensor",
    }
    ROOMS = ("书房", "客厅", "卧室", "厨房", "卫生间", "study", "living_room", "bedroom")
    SCENARIOS = {
        "睡眠": "sleep", "睡觉": "sleep", "睡眠模式": "sleep",
        "离家": "away", "出门": "away", "离家模式": "away",
        "节能": "energy_save", "节能模式": "energy_save",
    }
    ACTIONS = {
        "打开": "on", "开启": "on", "开灯": "on", "开风扇": "on", "on": "on",
        "关闭": "off", "关掉": "off", "关上": "off", "off": "off",
        "查询": "query", "查看": "query", "状态": "query", "读取": "query",
    }
    LATEST_INTENT_KEYWORDS = ("最新", "最近", "当前", "目前", "现有", "在线")
    YEAR_REGEX = re.compile(r"(\d{4})\s*年")

    def analyze(self, query: str) -> Dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return {
                "domain": None, "filters": {}, "has_temporal_constraint": False,
                "wants_latest": False, "temporal_mode": "none", "entities": {},
            }
        text = query.strip()
        filters = self._extract_filters(text)
        wants_latest = any(keyword in text.lower() for keyword in self.LATEST_INTENT_KEYWORDS)
        has_time = bool(filters.get("year") or filters.get("quarter"))
        return {
            "domain": "smart_home" if self._route_domain(text) else None,
            "filters": filters,
            "has_temporal_constraint": has_time,
            "wants_latest": wants_latest,
            "temporal_mode": "specific" if has_time else ("latest" if wants_latest else "none"),
            "entities": self._extract_entities(text, filters),
        }

    def _route_domain(self, query: str) -> Optional[str]:
        return "smart_home" if any(keyword.lower() in query.lower() for keyword in self.DOMAIN_KEYWORDS["smart_home"]) else None

    def _extract_filters(self, query: str) -> Dict[str, str]:
        filters: Dict[str, str] = {}
        year = self.YEAR_REGEX.search(query)
        if year:
            filters["year"] = year.group(1)
        lower_query = query.lower()
        for device_id, names in self.DEVICE_PATTERNS.items():
            if any(name.lower() in lower_query for name in names):
                filters["device_id"] = device_id
                break
        for name, device_type in self.DEVICE_TYPES.items():
            if name.lower() in lower_query:
                filters["device_type"] = device_type
                break
        for room in self.ROOMS:
            if room.lower() in lower_query:
                filters["room"] = room
                break
        for name, scenario in self.SCENARIOS.items():
            if name.lower() in lower_query:
                filters["scenario"] = scenario
                break
        for name, action in self.ACTIONS.items():
            if name.lower() in lower_query:
                filters["action"] = action
                break
        return filters

    def _extract_entities(self, query: str, filters: Dict[str, str]) -> Dict[str, Any]:
        del query
        return {key: filters[key] for key in ("device_id", "room", "scenario") if key in filters}

    def build_metadata_filter(self, query_meta: Dict[str, Any]) -> Optional[Dict[str, str]]:
        filters = query_meta.get("filters", {})
        supported = ("device_id", "device_type", "room", "scenario", "doc_type", "year")
        metadata_filter = {key: filters[key] for key in supported if filters.get(key) is not None}
        return metadata_filter or None

    def build_temporal_filter(self, query_meta: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """返回家居知识版本的时间过滤条件。"""
        year = query_meta.get("filters", {}).get("year")
        return {"effective_date": f"{year}-01-01", "expiry_date": f"{year}-12-31"} if year else None


query_analyzer = QueryAnalyzer()
