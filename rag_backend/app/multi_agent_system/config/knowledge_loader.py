"""
知识库/风险规则加载器

从 JSON 配置文件加载专业知识库和风险评估规则。
运营人员可直接编辑 JSON 文件更新规则，无需修改代码。

配置文件路径（相对于本模块）：
    - knowledge_base.json: 专业知识库规则
    - risk_rules.json: 风险评估规则
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 配置文件目录
_CONFIG_DIR = Path(__file__).parent


def _load_json_file(filename: str) -> Dict[str, Any]:
    """加载 JSON 配置文件，返回字典；若失败返回空字典。"""
    filepath = _CONFIG_DIR / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("成功加载配置: %s (keys=%s)", filename, [k for k in data if not k.startswith("_")])
        return data
    except FileNotFoundError:
        logger.warning("配置文件不存在: %s", filepath)
    except json.JSONDecodeError as e:
        logger.error("配置文件 JSON 解析失败: %s, error=%s", filepath, e)
    except Exception as e:
        logger.error("加载配置文件失败: %s, error=%s", filepath, e)
    return {}


def _get_fallback_knowledge(specialty: str) -> List[Dict[str, Any]]:
    """当配置文件不可用时，返回内置的兜底知识规则。"""
    fallbacks = {
        "home_butler": [
            {"rule_id": "HOME_001", "category": "设备白名单", "description": "仅允许控制已注册设备与固定动作", "risk_level": "high"},
        ],
        "environment": [
            {"rule_id": "ENV_001", "category": "传感器时效", "description": "环境数据必须标注时间与来源", "risk_level": "medium"},
        ],
        "device_control": [
            {"rule_id": "DEV_001", "category": "幂等控制", "description": "重复请求不重复执行", "risk_level": "medium"},
        ],
        "comfort": [
            {"rule_id": "COM_001", "category": "自动联动", "description": "自动模式根据温度、烟雾、火焰和有人状态执行固定联动", "risk_level": "low"},
        ],
    }
    return fallbacks.get(specialty, [])


def _get_fallback_risk_rules(specialty: str) -> List[Dict[str, Any]]:
    """当配置文件不可用时，返回内置的兜底风险规则。"""
    fallbacks = {
        "home_butler": [
            {"pattern": "任意Topic|绕过安全", "risk_score": 1.0, "risk_level": "critical"},
        ],
        "environment": [
            {"pattern": "传感器数据异常", "risk_score": 0.7, "risk_level": "high"},
        ],
        "device_control": [
            {"pattern": "非法设备指令", "risk_score": 0.9, "risk_level": "critical"},
        ],
        "comfort": [
            {"pattern": "自动联动条件不明确|忽略传感器故障", "risk_score": 0.6, "risk_level": "medium"},
        ],
    }
    return fallbacks.get(specialty, [])


def load_knowledge_base(specialty: str) -> List[Dict[str, Any]]:
    """加载指定专业领域的知识库规则。

    优先从 knowledge_base.json 读取，失败时回退到内置兜底规则。
    """
    data = _load_json_file("knowledge_base.json")
    rules = data.get(specialty)
    if rules:
        logger.debug("从配置文件加载 %s 知识库: %d 条规则", specialty, len(rules))
        return rules

    logger.warning("配置文件未找到 %s 知识库，使用内置兜底规则", specialty)
    return _get_fallback_knowledge(specialty)


def load_risk_rules(specialty: str) -> List[Dict[str, Any]]:
    """加载指定专业领域的风险评估规则。

    优先从 risk_rules.json 读取，失败时回退到内置兜底规则。
    """
    data = _load_json_file("risk_rules.json")
    rules = data.get(specialty)
    if rules:
        logger.debug("从配置文件加载 %s 风险规则: %d 条规则", specialty, len(rules))
        return rules

    logger.warning("配置文件未找到 %s 风险规则，使用内置兜底规则", specialty)
    return _get_fallback_risk_rules(specialty)
