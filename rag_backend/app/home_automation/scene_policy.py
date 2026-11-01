"""场景预设对应的固定工具白名单。"""

from .device_models import HomeScenarioName

QUERY_TOOLS = frozenset(
    {
        "get_device_status",
        "list_home_devices",
        "read_home_environment",
        "get_environment_history",
        "get_home_alerts",
        "get_door_lock_status",
        "get_environment_thresholds",
        "get_automation_mode",
        "run_home_scenario",
    }
)
DOOR_TOOLS = frozenset(
    {
        "open_door",
        "close_door",
        "unlock_door",
        "lock_door",
        "engage_deadbolt",
        "release_deadbolt",
    }
)
SCENE_TOOL_ALLOWLIST = {
    HomeScenarioName.NORMAL: frozenset(
        {
            "set_light_state",
            "set_fan_state",
            "set_sprinkler_pump_state",
            "set_alarm_buzzer_state",
            "set_automation_mode",
            "set_environment_threshold",
            *DOOR_TOOLS,
        }
    ),
    HomeScenarioName.SLEEP: frozenset(
        {
            "set_light_state",
            "set_fan_state",
            "set_alarm_buzzer_state",
            *DOOR_TOOLS,
        }
    ),
    HomeScenarioName.AWAY: frozenset(
        {
            "set_sprinkler_pump_state",
            "set_alarm_buzzer_state",
            *DOOR_TOOLS,
        }
    ),
}


def tool_allowed(scene: HomeScenarioName, tool_name: str) -> bool:
    """判断工具在当前场景是否允许被人工调用。"""

    return tool_name in QUERY_TOOLS or tool_name in SCENE_TOOL_ALLOWLIST[scene]


def blocked_reason(scene: HomeScenarioName, tool_name: str) -> str:
    """返回稳定、可展示的场景拦截原因。"""

    return f"Tool {tool_name} is not allowed in {scene.value} scene"


__all__ = ["DOOR_TOOLS", "QUERY_TOOLS", "SCENE_TOOL_ALLOWLIST", "blocked_reason", "tool_allowed"]
