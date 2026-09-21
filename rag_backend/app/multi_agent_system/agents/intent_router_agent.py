"""
意图路由智能体 (Intent Router Agent)
融合了接待智能体和意图识别智能体的功能，统一处理用户输入

职责：
1. 快速简单检测（正则匹配，不调用LLM）
2. 意图分类 + 实体提取 + 复杂度评估（调用LLM）
3. 路由决策
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.prompt_service import PromptEngine
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt
from app.multi_agent_system.clarification_service import (
    ClarificationService,
    ClarificationRequest,
)

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


class IntentCategory(str, Enum):
    """意图分类枚举"""
    GREETING = "greeting"
    CHIT_CHAT = "chit_chat"
    KNOWLEDGE_QUERY = "knowledge_query"
    DOCUMENT_SEARCH = "document_search"
    REPORT_GENERATION = "report_generation"
    DATA_EXTRACTION = "data_extraction"
    COMPLEX_TASK = "complex_task"
    MULTI_SPECIALIST = "multi_specialist"
    HOME_CONTROL = "home_control"
    DEVICE_SWITCH = "device_switch"
    DEVICE_STATUS = "device_status"
    SENSOR_READING = "sensor_reading"
    COMFORT_ASSESSMENT = "comfort_assessment"
    SLEEP_MODE = "sleep_mode"
    ENERGY_SAVE = "energy_save"
    UNKNOWN = "unknown"


class ComplexityLevel(str, Enum):
    """复杂度等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class RoutingStrategy(str, Enum):
    """路由策略"""
    DIRECT_ANSWER = "direct_answer"
    RAG_RETRIEVAL = "rag_retrieval"
    SINGLE_SPECIALIST = "single_specialist"
    MULTI_SPECIALIST_PARALLEL = "multi_specialist_parallel"
    MULTI_SPECIALIST_SEQUENTIAL = "multi_specialist_sequential"
    REPORT_QUEUE = "report_queue"


class ExtractedEntity(BaseModel):
    """提取的实体"""
    entity_type: str = Field(..., description="实体类型")
    entity_value: str = Field(..., description="实体值")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    source_text: str = Field(..., description="来源文本")


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    intent: IntentCategory = Field(..., description="主要意图")
    sub_intent: Optional[IntentCategory] = Field(None, description="子意图")
    entities: List[ExtractedEntity] = Field(default_factory=list, description="提取的实体")
    complexity: ComplexityLevel = Field(..., description="复杂度")
    requires_specialists: List[str] = Field(default_factory=list, description="需要的专家列表")
    routing_strategy: RoutingStrategy = Field(..., description="路由策略")
    suggested_params: Dict[str, Any] = Field(default_factory=dict, description="建议参数")
    confidence: float = Field(..., ge=0.0, le=1.0, description="整体置信度")
    needs_human_review: bool = Field(False, description="是否需要人工审核")
    reasoning: str = Field("", description="推理过程")
    needs_report_generation: bool = Field(False, description="是否需要生成报告")


class IntentRoutingResult(BaseModel):
    """意图路由结果（统一返回类型）"""
    is_simple: bool = Field(False, description="是否为简单问题")
    simple_response: Optional[str] = Field(None, description="简单问题的回答")
    intent_result: Optional[IntentAnalysisResult] = Field(None, description="意图分析结果")
    clarification_request: Optional[ClarificationRequest] = Field(None, description="追问请求（当输入模糊时）")
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )


class IntentRouterAgent(BaseAgent):
    """
    意图路由智能体
    
    融合了ReceptionistAgent和IntentAgent的功能：
    1. 快速简单检测（正则，不调用LLM）
    2. 意图分类+实体提取+复杂度评估（调用LLM）
    3. 路由决策
    
    优势：
    - 减少LLM调用次数（从2次减少到1-2次）
    - 消除职责重复
    - 简化编排器逻辑
    """
    
    SIMPLE_PATTERNS = {
        "greeting": r"^(你好|您好|hi|hello|嗨|hey)[\s,，.]*",
        "weather": r".*?(天气|weather).*",
        "time": r".*?(时间|time|现在几点).*",
        "help": r".*?(help|帮助|怎么用|如何使用).*",
        "thanks": r"^.*?(谢谢|thanks|感谢)[\s,，.]*",
        "config_query": r".*?(有没有打开|是否启用|开启了吗|关闭了吗|当前状态|当前配置|我的设置|会话状态)",
        "skill_query": r"^(?=.*(?:技能|skill|能力))(?=.*(?:有哪|是什么|有哪些|有什么|列出|介绍|展示)).*",
    }
    SKILL_QUERY_FALLBACK = (
        "我具备以下智能家居能力：\n\n"
        "**设备控制**：查询设备状态、打开或关闭已注册设备、校验控制指令\n"
        "**环境感知**：读取温度、湿度、烟雾、火焰和有人状态\n"
        "**自动联动**：切换手动/自动模式并调整环境阈值\n"
        "**安全保障**：设备白名单、幂等请求、离线拒绝和 MQTT 回执校验\n\n"
        "请描述您要查询或控制的设备，我会先核对状态与安全规则。"
    )
    
    ENTITY_PATTERNS = {
        "money": {
            "patterns": [
                r"([¥$€£]?\d+(?:,\d{3})*(?:\.\d{2})?)",
                r"(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:万|亿|千|百)?\s*(?:元|美元|欧元|英镑))",
            ],
            "entity_type": "金额"
        },
        "percentage": {
            "patterns": [
                r"(\d+(?:\.\d+)?%)",
                r"百分之(\d+(?:\.\d+)?)",
            ],
            "entity_type": "百分比"
        },
        "date": {
            "patterns": [
                r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"(\d{4}年\d{1,2}月)",
            ],
            "entity_type": "日期"
        },
        "device": {
            "patterns": [
                r"(desk_light|desk_fan|书桌灯|风扇|灯|传感器)",
            ],
            "entity_type": "设备"
        },
    }
    
    COMPLEXITY_RULES = {
        ComplexityLevel.LOW: [
            r"(你好|您好|hi|hello)",
            r"(现在几点|今天几号|当前时间)",
            r"(什么是|什么叫|定义)",
        ],
        ComplexityLevel.MEDIUM: [
            r"(计算|分析|查询)",
            r"(如何|怎么|怎样)",
        ],
        ComplexityLevel.HIGH: [
            r"(比较|对比|差异)",
            r"(优化|改进|提升)",
        ],
        ComplexityLevel.VERY_HIGH: [
            r"(报告|报表|生成.*报告)",
            r"(审查|审计|检查)",
        ]
    }
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        confidence_threshold: float = 0.7,
        max_iterations: int = 3,
        timeout: float = 30.0,
        specialist_descriptions: str = "",
        intent_mapping: Dict[str, str] = None,
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
    ):
        """
        初始化意图路由智能体

        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            confidence_threshold: 置信度阈值
            max_iterations: 最大迭代次数
            timeout: 超时时间
            specialist_descriptions: 专家能力描述
            intent_mapping: 意图到专家的映射
            skill_registry: 技能注册表（可选）
        """
        self.confidence_threshold = confidence_threshold
        self.prompt_engine = PromptEngine()
        self._specialist_descriptions = specialist_descriptions
        self._intent_mapping = intent_mapping or {}
        self._classification_prompt_cache: Optional[str] = None

        self.clarification_service = ClarificationService(
            min_query_length=5,
            confidence_threshold=0.6,
            enable_clarification=True
        )

        system_prompt = self._load_system_prompt()

        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout,
            skill_registry=skill_registry,  # 🆕 技能系统
        )
        
        print("🎯 [意图路由智能体] 初始化完成")
        print("   - 快速简单检测: 启用")
        print("   - LLM意图分类: 启用")
        print("   - 置信度阈值: " + str(self.confidence_threshold))
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            home_prompt = Path(__file__).resolve().parents[2] / "prompts" / "agents" / "intent_router" / "home_system.md"
            if home_prompt.exists():
                return home_prompt.read_text(encoding="utf-8")
            return load_agent_prompt(
                agent_name="intent_router",
                filename="system.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            logger.debug(f"[意图路由智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        mapping_text = self._format_intent_mapping()
        return {
            "intent_categories": [c.value for c in IntentCategory],
            "complexity_levels": [c.value for c in ComplexityLevel],
            "routing_strategies": [c.value for c in RoutingStrategy],
            "specialist_descriptions": self._specialist_descriptions or "暂无专家配置",
            "intents_specialist_mapping": mapping_text,
        }
    
    def _format_intent_mapping(self) -> str:
        """将意图映射格式化为可读文本"""
        if not self._intent_mapping:
            return "暂无映射配置"
        lines = []
        for intent, specialist in sorted(self._intent_mapping.items()):
            lines.append(f"- **{intent}** → {specialist}")
        return "\n".join(lines)
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """# 智能家居意图路由智能体

你负责识别用户的智能家居意图，并选择知识库检索、设备查询、设备控制或场景联动路径。

意图类别包括：greeting、chit_chat、knowledge_query、document_search、home_control、
device_switch、device_status、sensor_reading、comfort_assessment、sleep_mode、energy_save、
complex_task、multi_specialist 和 unknown。

涉及设备控制时，必须保留设备标识、目标状态、请求幂等标识，并遵守设备白名单、在线状态、
参数范围、过期时间和设备回执规则。无法确认设备或安全条件时，应路由到澄清或人工复核。

输出 JSON：intent、sub_intent、entities、complexity、requires_specialists、routing_strategy、
confidence、needs_human_review、reasoning。"""
    
    def _is_simple_greeting(self, text: str) -> Optional[str]:
        """检测简单问候语（正则匹配，不调用LLM）"""
        text_lower = text.lower().strip()
        
        if re.search(self.SIMPLE_PATTERNS["greeting"], text_lower):
            return self._build_greeting_response()
        
        if re.search(self.SIMPLE_PATTERNS["thanks"], text_lower):
            return "不客气！很高兴能帮助您。请问还有什么其他问题吗？"
        
        if re.search(self.SIMPLE_PATTERNS["help"], text_lower):
            return self._build_help_response()
        
        if re.search(self.SIMPLE_PATTERNS["config_query"], text_lower):
            return "__CONFIG_QUERY__"

        if re.search(self.SIMPLE_PATTERNS["skill_query"], text_lower):
            return self.SKILL_QUERY_FALLBACK

        return None
    
    def _build_greeting_response(self) -> str:
        """构建问候响应"""
        from datetime import datetime
        hour = datetime.now().hour
        
        if hour < 12:
            time_greeting = "上午好"
        elif hour < 18:
            time_greeting = "下午好"
        else:
            time_greeting = "晚上好"
        
        return f"{time_greeting}！欢迎使用智能家居助手。我可以帮您查询设备状态、执行安全控制并管理家居场景。请问需要什么帮助？"
    
    def _build_help_response(self) -> str:
        """构建帮助响应"""
        return """📖 **智能助手使用指南**

我可以帮助您处理以下智能家居问题：

**🏠 设备控制**
- 查询已注册设备及在线状态
- 打开或关闭书桌灯、风扇等设备
- 按 request_id 保证重复请求不重复执行

**🌡️ 环境感知**
- 查询温度、湿度、烟雾、火焰和有人传感器
- 识别过期或异常读数

**🌙 场景联动**
- 手动/自动模式和阈值联动建议
- MQTT 消息收发与设备回执

**📚 知识库问答**
- 检索智能家居设备说明和安全规则

请直接输入您的问题，我会尽力为您解答！"""

    def _extract_entities(self, text: str) -> List[ExtractedEntity]:
        """提取实体（正则匹配）"""
        entities = []
        
        for entity_name, config in self.ENTITY_PATTERNS.items():
            for pattern in config["patterns"]:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append(ExtractedEntity(
                        entity_type=config["entity_type"],
                        entity_value=match.group(1) if match.groups() else match.group(),
                        confidence=0.9,
                        source_text=text[max(0, match.start()-10):min(len(text), match.end()+10)]
                    ))
        
        return entities
    
    def _assess_complexity(
        self,
        text: str,
        intent: IntentCategory,
        entities: List[ExtractedEntity]
    ) -> ComplexityLevel:
        """评估问题复杂度"""
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return ComplexityLevel.LOW
        
        if intent == IntentCategory.REPORT_GENERATION:
            return ComplexityLevel.VERY_HIGH
        
        complexity_score = 0
        
        for level, patterns in self.COMPLEXITY_RULES.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    complexity_score += {
                        ComplexityLevel.LOW: 1,
                        ComplexityLevel.MEDIUM: 2,
                        ComplexityLevel.HIGH: 3,
                        ComplexityLevel.VERY_HIGH: 4
                    }[level]
        
        complexity_score += len(entities) * 0.5
        
        if "和" in text or "或" in text or "还是" in text:
            complexity_score += 2
        
        if complexity_score <= 2:
            return ComplexityLevel.LOW
        elif complexity_score <= 4:
            return ComplexityLevel.MEDIUM
        elif complexity_score <= 6:
            return ComplexityLevel.HIGH
        else:
            return ComplexityLevel.VERY_HIGH
    
    def _determine_routing_strategy(
        self,
        intent: IntentCategory,
        complexity: ComplexityLevel
    ) -> RoutingStrategy:
        """决定路由策略"""
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return RoutingStrategy.DIRECT_ANSWER
        
        if intent in [IntentCategory.KNOWLEDGE_QUERY, IntentCategory.DOCUMENT_SEARCH]:
            return RoutingStrategy.RAG_RETRIEVAL
        
        if intent == IntentCategory.REPORT_GENERATION:
            return RoutingStrategy.REPORT_QUEUE
        
        if intent in [IntentCategory.COMPLEX_TASK, IntentCategory.MULTI_SPECIALIST]:
            return RoutingStrategy.MULTI_SPECIALIST_PARALLEL
        
        if complexity in [ComplexityLevel.LOW, ComplexityLevel.MEDIUM]:
            return RoutingStrategy.SINGLE_SPECIALIST
        
        if complexity in [ComplexityLevel.HIGH, ComplexityLevel.VERY_HIGH]:
            return RoutingStrategy.MULTI_SPECIALIST_PARALLEL
        
        return RoutingStrategy.SINGLE_SPECIALIST
    
    def _determine_required_specialists(
        self,
        intent: IntentCategory,
        routing_strategy: RoutingStrategy
    ) -> List[str]:
        """确定需要的专家"""
        intent_specialist_map = {
            IntentCategory.HOME_CONTROL: ["home_butler"],
            IntentCategory.DEVICE_SWITCH: ["device_control"],
            IntentCategory.DEVICE_STATUS: ["device_control"],
            IntentCategory.SENSOR_READING: ["environment"],
            IntentCategory.COMFORT_ASSESSMENT: ["environment"],
            IntentCategory.SLEEP_MODE: ["comfort"],
            IntentCategory.ENERGY_SAVE: ["comfort"],
        }
        
        specialists = intent_specialist_map.get(intent, [])
        
        if intent in [IntentCategory.COMPLEX_TASK, IntentCategory.MULTI_SPECIALIST]:
            specialists = ["home_butler", "environment", "device_control"]
        
        if routing_strategy in [
            RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
            RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
        ]:
            if not specialists:
                specialists = ["home_butler"]
        
        return specialists if specialists else ["general"]
    
    def _should_require_human_review(
        self,
        confidence: float,
        complexity: ComplexityLevel,
        intent: IntentCategory
    ) -> bool:
        """判断是否需要人工审核"""
        if confidence < self.confidence_threshold:
            return True
        
        if complexity == ComplexityLevel.VERY_HIGH:
            return True
        
        if intent == IntentCategory.UNKNOWN:
            return True
        
        return False
    
    def _classify_intent_rule_based(
        self,
        text: str
    ) -> Dict[str, Any]:
        """基于规则的意图分类"""
        text_lower = text.lower()

        # 智能家居规则始终启用，避免环境变量导致业务路由回到旧领域。
        home_rules = (
            (("打开", "开启", "关闭", "关掉", "开灯", "关灯", "开风扇", "关风扇", "on", "off"),
             ("灯", "light", "风扇", "fan"), IntentCategory.DEVICE_SWITCH),
            (("状态", "列表", "在线", "离线"), ("设备", "灯", "风扇", "device", "light", "fan"), IntentCategory.DEVICE_STATUS),
            (("温度", "湿度", "烟雾", "火焰", "有人", "传感器", "环境"), (), IntentCategory.SENSOR_READING),
            (("手动", "自动", "阈值"), (), IntentCategory.HOME_CONTROL),
        )
        for action_words, object_words, home_intent in home_rules:
            if any(word in text_lower for word in action_words) and (
                not object_words or any(word in text_lower for word in object_words)
            ):
                return {
                    "intent": home_intent,
                    "confidence": 0.95,
                    "reasoning": "智能家居领域规则命中",
                    "needs_report_generation": False,
                }

        report_keywords = [
            "生成报告", "生成一份报告", "输出一份报告",
            "给我一份报告", "给我报告", "需要报告",
            "生成分析报告", "生成家居报告",
        ]
        needs_report = any(kw in text_lower for kw in report_keywords)
        
        keyword_map = {
            "报告": IntentCategory.REPORT_GENERATION,
            "查询": IntentCategory.KNOWLEDGE_QUERY,
            "知识库": IntentCategory.KNOWLEDGE_QUERY,
            "设备": IntentCategory.DEVICE_STATUS,
            "灯": IntentCategory.DEVICE_STATUS,
            "风扇": IntentCategory.DEVICE_STATUS,
            "传感器": IntentCategory.SENSOR_READING,
            "舒适": IntentCategory.COMFORT_ASSESSMENT,
        }
        
        for keyword, intent in keyword_map.items():
            if keyword in text_lower:
                return {
                    "intent": intent,
                    "confidence": 0.8,
                    "reasoning": f"检测到关键词: {keyword}",
                    "needs_report_generation": needs_report
                }
        
        return {
            "intent": IntentCategory.KNOWLEDGE_QUERY,
            "confidence": 0.5,
            "reasoning": "未能明确分类，归类为知识查询",
            "needs_report_generation": needs_report
        }
    
    async def _classify_intent_llm(
        self,
        text: str,
        entities: List[ExtractedEntity],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用LLM进行意图分类"""
        entity_str = ", ".join([
            f"{e.entity_type}: {e.entity_value}"
            for e in entities[:5]
        ])
        
        classification_prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system" / "intent_classification_prompt.md"
        
        if classification_prompt_path.exists():
            try:
                with open(classification_prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
            except Exception:
                prompt_template = None
        else:
            prompt_template = None
        
        if not prompt_template:
            prompt_template = """分析以下用户输入的意图：

用户输入：{user_input}

已识别的实体：{entities}

请返回JSON格式的意图分析：
{{
  "intent": "意图类别",
  "sub_intent": "子意图（可选）",
  "params": {{"建议参数"}},
  "confidence": 0.0-1.0,
  "reasoning": "推理过程"
}}

注意：
1. 如果是问候语，返回 intent: "greeting"
2. 如果是闲聊，返回 intent: "chit_chat"
3. 如果需要多个专家，返回 intent: "multi_specialist"
4. 置信度要基于实体匹配和上下文判断
5. 如果用户要求生成报告，设置 needs_report_generation: true"""
        
        text_lower = text.lower()
        report_keywords = [
            "生成报告", "生成一份报告", "输出一份报告",
            "给我一份报告", "给我报告", "需要报告",
            "生成分析报告", "生成家居报告",
            "生成分析文档", "生成分析材料", "请生成报告"
        ]
        needs_report = any(kw in text_lower for kw in report_keywords)
        
        prompt = prompt_template.format(
            user_input=text,
            entities=entity_str or "无"
        )
        
        try:
            response = await self.llm_adapter.agenerate(
                prompts=[prompt],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.content.strip()
            
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(result_text)
            
            if "intent" in result and isinstance(result["intent"], str):
                try:
                    result["intent"] = IntentCategory(result["intent"])
                except ValueError:
                    result["intent"] = IntentCategory.UNKNOWN
                
                if result.get("sub_intent"):
                    try:
                        result["sub_intent"] = IntentCategory(result["sub_intent"])
                    except ValueError:
                        result["sub_intent"] = None
            
            confidence = result.get("confidence", 0.0)
            detected_intent = result.get("intent", IntentCategory.UNKNOWN)
            
            generic_intents = {
                IntentCategory.UNKNOWN,
                IntentCategory.MULTI_SPECIALIST,
                IntentCategory.COMPLEX_TASK,
                IntentCategory.KNOWLEDGE_QUERY
            }
            
            rule_result = self._classify_intent_rule_based(text)
            rule_confidence = rule_result.get("confidence", 0.0)
            
            should_use_rule = False
            if detected_intent in generic_intents and rule_confidence >= 0.8:
                should_use_rule = True
                print("⚠️ [意图路由智能体] LLM返回通用意图，使用规则匹配补充")
            elif confidence <= self.confidence_threshold and rule_confidence > confidence:
                should_use_rule = True
                print(f"⚠️ [意图路由智能体] 置信度({confidence})<=阈值({self.confidence_threshold})，使用规则匹配补充")
            
            if should_use_rule:
                result = rule_result
            
            result["needs_report_generation"] = needs_report
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️ [意图路由智能体] LLM返回格式错误，使用规则匹配: {e}")
            return self._classify_intent_rule_based(text)
        except Exception as e:
            print(f"⚠️ [意图路由智能体] LLM分类失败，使用规则匹配: {e}")
            return self._classify_intent_rule_based(text)
    
    async def run(
        self,
        user_input: str,
        history: List[Dict] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> IntentRoutingResult:
        """
        执行意图路由主流程
        
        步骤：
        1. 快速检测简单问题（正则，不调用LLM）
        2. 如果不是简单问题，调用LLM进行意图分类
        3. 实体提取 + 复杂度评估 + 路由决策
        
        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            **kwargs: 其他参数
            
        Returns:
            IntentRoutingResult: 统一的路由结果
        """
        print(f"🎯 [意图路由智能体] 处理输入: {user_input[:50]}...")
        
        simple_response = self._is_simple_greeting(user_input)
        if simple_response:
            print("✅ [意图路由智能体] 简单问题，直接返回")
            return IntentRoutingResult(
                is_simple=True,
                simple_response=simple_response,
                intent_result=None
            )
        
        entities = self._extract_entities(user_input)
        
        rule_based_result = self._classify_intent_rule_based(user_input)
        if rule_based_result["confidence"] >= 0.9:
            print(f"✅ [意图路由智能体] 规则匹配命中，跳过LLM: {rule_based_result['intent'].value}")
            intent_result_dict = rule_based_result
        else:
            intent_result_dict = await self._classify_intent_llm(user_input, entities, context or {})
        
        complexity = self._assess_complexity(
            user_input,
            intent_result_dict["intent"],
            entities
        )
        
        routing_strategy = self._determine_routing_strategy(
            intent_result_dict["intent"],
            complexity
        )
        
        specialists = self._determine_required_specialists(
            intent_result_dict["intent"],
            routing_strategy
        )
        
        needs_review = self._should_require_human_review(
            intent_result_dict["confidence"],
            complexity,
            intent_result_dict["intent"]
        )
        
        intent_result = IntentAnalysisResult(
            intent=intent_result_dict["intent"],
            sub_intent=intent_result_dict.get("sub_intent"),
            entities=entities,
            complexity=complexity,
            requires_specialists=specialists,
            routing_strategy=routing_strategy,
            suggested_params=intent_result_dict.get("params", {}),
            confidence=intent_result_dict["confidence"],
            needs_human_review=needs_review,
            reasoning=intent_result_dict.get("reasoning", ""),
            needs_report_generation=intent_result_dict.get("needs_report_generation", False)
        )
        
        print("✅ [意图路由智能体] 分析完成")
        print(f"   意图: {intent_result.intent.value}")
        print(f"   复杂度: {intent_result.complexity.value}")
        print(f"   路由: {intent_result.routing_strategy.value}")
        print(f"   置信度: {intent_result.confidence:.2f}")
        
        intent_str = (
            intent_result.intent.value 
            if hasattr(intent_result.intent, 'value') 
            else str(intent_result.intent)
        )
        routing_str = (
            intent_result.routing_strategy.value
            if hasattr(intent_result.routing_strategy, 'value')
            else str(intent_result.routing_strategy)
        )
        
        clarification = await self.clarification_service.detect_ambiguous_input(
            query=user_input,
            intent=intent_str,
            confidence=intent_result.confidence,
            entities=[e.model_dump() for e in intent_result.entities],
            routing_strategy=routing_str
        )
        
        return IntentRoutingResult(
            is_simple=False,
            simple_response=None,
            intent_result=intent_result,
            clarification_request=clarification
        )
    
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs):
        """流式执行（暂不支持，返回完整结果）"""
        result = await self.run(user_input, history, **kwargs)
        yield result
