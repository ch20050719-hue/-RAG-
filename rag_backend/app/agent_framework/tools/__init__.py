# app/agent_framework/tools/__init__.py

"""
工具管理模块

提供工具注册、调用、工具链和混合执行功能
"""

from .tool_manager import ToolManager
from .langchain_compat import LangChainCompatLayer
from .tool_chain import ToolChain, ToolChainManager, ChainStep, ChainStepType
from .hybrid_manager import HybridToolManager, ExecutionMode

from .base import ToolBase
from .document_retrieval_tools import DocumentChunkRetrievalTool

__all__ = [
    # 基础组件
    "ToolManager",
    "ToolBase",
    "LangChainCompatLayer",
    
    # 工具链
    "ToolChain",
    "ToolChainManager", 
    "ChainStep",
    "ChainStepType",
    
    # 混合管理
    "HybridToolManager",
    "ExecutionMode",
    
    # 文档检索工具
    "DocumentChunkRetrievalTool",
]
