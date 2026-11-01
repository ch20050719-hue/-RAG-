# app/agent_framework/__init__.py

"""
自定义 Agent 框架

一个简洁、易懂的 Agent 实现，支持多种推理模式：
- ReAct: Reasoning and Acting
- Plan-and-Solve: 规划执行模式
- Reflect: 反思改进模式
- Output Review: 输出质量审查
- Agent Orchestration: 多智能体调度

设计理念：
- 简单优于复杂
- 核心代码易于理解
- 支持多种专业智能体协作
- 统一的质量把控
"""

from .core.base_agent import BaseAgent
from .core.react_agent import ReActAgent
from .core.plan_agent import PlanAgent
from .core.reflect_agent import ReflectAgent
from .components import ResultSynthesizer
from .tools.tool_manager import ToolManager
from .llm.zhipu_adapter import ZhipuAdapter

__version__ = "1.2.0"

__all__ = [
    # 核心
    "BaseAgent",
    "ReActAgent",
    "PlanAgent",
    "ReflectAgent",
    
    # 智能组件
    "ResultSynthesizer",
    
    # 工具
    "ToolManager",
    "ZhipuAdapter",
]
