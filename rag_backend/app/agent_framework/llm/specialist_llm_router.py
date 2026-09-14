"""智能家居 Agent 的 LLM 路由器。"""

import logging
from typing import Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant_settings import TenantSettings
from .agent_llm_config import AgentLLMConfig, AgentLLMConfigManager, AgentType
from .agent_adapter_factory import AgentLLMAdapterFactory
from .base_adapter import BaseLLMAdapter

logger = logging.getLogger(__name__)


class SpecialistLLMRouter:
    """按家居角色、租户覆盖和默认配置选择 LLM。"""

    @classmethod
    def _get_provider_for_type(cls, agent_type: AgentType) -> str:
        return settings.get_llm_provider_for_agent(agent_type.value)

    @staticmethod
    def _get_model_for_provider(provider: str) -> Optional[str]:
        return {
            "deepseek": "deepseek/deepseek-chat-v3-0324",
            "qwen": "qwen/qwen3.6-plus:free",
            "zhipu": "glm-4-flash",
            "gpt": "openai/gpt-4o-mini",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-sonnet-20240229",
            "minimax": "MiniMax-Text-01",
        }.get(provider.lower())

    @classmethod
    def _create(cls, agent_type: AgentType) -> BaseLLMAdapter:
        provider = cls._get_provider_for_type(agent_type)
        return AgentLLMAdapterFactory.create_adapter(AgentLLMConfig(agent_type=agent_type, provider=provider, model=cls._get_model_for_provider(provider), enabled=True))

    @classmethod
    def get_default_adapter(cls) -> BaseLLMAdapter:
        provider = settings.LLM_PROVIDER or "zhipu"
        return AgentLLMAdapterFactory.create_adapter(AgentLLMConfig(agent_type=AgentType.REACT, provider=provider, model=cls._get_model_for_provider(provider), enabled=True))

    @classmethod
    def get_chat_adapter(cls) -> BaseLLMAdapter:
        return cls._create(AgentType.CHAT)

    @classmethod
    def get_greeting_adapter(cls) -> BaseLLMAdapter:
        return cls._create(AgentType.GREETING)

    @classmethod
    def get_home_adapter(cls) -> BaseLLMAdapter:
        return cls._create(AgentType.HOME_BUTLER)

    @classmethod
    async def get_adapter_for_specialist(cls, agent_type: AgentType, tenant_id: Optional[str] = None, db: Optional[AsyncSession] = None) -> BaseLLMAdapter:
        custom = await cls._get_tenant_agent_config(tenant_id, agent_type.value, db) if tenant_id and db else None
        if custom and custom.enabled:
            return AgentLLMAdapterFactory.create_adapter(custom)
        return cls._create(agent_type)

    @classmethod
    async def _get_tenant_agent_config(cls, tenant_id: str, agent_type: str, db: AsyncSession) -> Optional[AgentLLMConfig]:
        try:
            result = await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                return None
            config = AgentLLMConfigManager.load_from_extra_settings(tenant.extra_settings)
            return config.get_agent_config(agent_type)
        except Exception as exc:  # noqa: BLE001 - optional tenant override
            logger.warning("加载租户 LLM 配置失败: %s", exc)
            return None

    @classmethod
    def get_all_default_mappings(cls) -> Dict[str, tuple]:
        types = (AgentType.CHAT, AgentType.GREETING, AgentType.HOME_BUTLER, AgentType.ENVIRONMENT, AgentType.DEVICE_CONTROL, AgentType.COMFORT)
        return {item.value: (cls._get_provider_for_type(item), cls._get_model_for_provider(cls._get_provider_for_type(item))) for item in types}
