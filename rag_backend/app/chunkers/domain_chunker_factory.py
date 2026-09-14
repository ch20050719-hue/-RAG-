"""
领域切块工厂 (Domain Chunker Factory)

根据 domain 类型返回对应的领域切块器。
对调用方透明：调用方只需传 domain，不需要知道具体切块器实现。
"""

import logging
from app.chunkers.domains import SUPPORTED_DOCUMENT_DOMAINS

logger = logging.getLogger(__name__)


class DomainChunkerFactory:
    """
    领域切块工厂。

    用法：
        chunker = DomainChunkerFactory.get_chunker("smart_home")
        chunks = await chunker.chunk(structured_doc)
    """

    # 懒加载实例缓存
    _chunkers = {}

    @classmethod
    def get_chunker(cls, domain: str):
        """
        根据 domain 获取对应的领域切块器。

        Args:
            domain: 文档领域 (smart_home/general)

        Returns:
            领域切块器实例

        Raises:
            ValueError: 不支持的 domain
        """
        if domain not in cls._chunkers:
            cls._chunkers[domain] = cls._create_chunker(domain)
        return cls._chunkers[domain]

    @classmethod
    def _create_chunker(cls, domain: str):
        """创建领域切块器实例"""
        if domain in {"smart_home", "general"}:
            from app.chunkers.general_chunker import GeneralChunker

            chunker = GeneralChunker(domain=domain)
        else:
            raise ValueError(f"不支持的领域类型: {domain}")

        logger.info(f"[DomainChunkerFactory] 创建领域切块器: {domain}")
        return chunker

    @classmethod
    def get_supported_domains(cls) -> list:
        """返回所有支持的领域列表"""
        return list(SUPPORTED_DOCUMENT_DOMAINS)


# 全局单例
domain_chunker_factory = DomainChunkerFactory()
