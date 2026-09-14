"""
文本切块器模块 (v2)
支持领域感知切分、节点关系、元数据注入等高级能力

模块结构：
- base_chunker: ChunkResult 数据类 + ChunkStrategy 抽象基类
- domain_detector: 领域检测器
- domain_chunker_factory: 领域切块工厂
- general_chunker: 通用领域切块策略
- ast_sanitizer: AST 净化器
- metadata_injector: AST 上下文栈元数据注入
- entity_resolver: 家居实体元数据解析器
- summary_generator: PARENT 节点摘要生成器
- relationship_builder: 节点关系构建器
- structured_document_chunker: 结构化文档切块器（保留）
- plain_text_chunker: 纯文本切块器（保留）
"""

from .base_chunker import ChunkStrategy, ChunkResult
from .domain_detector import DomainDetector, domain_detector
from .domain_chunker_factory import DomainChunkerFactory, domain_chunker_factory
from .general_chunker import GeneralChunker, general_chunker
from .ast_sanitizer import ASTSanitizer
from .metadata_injector import MetadataInjector, ContextStack, metadata_injector
from .entity_resolver import EntityResolver, entity_resolver
from .summary_generator import SummaryGenerator, summary_generator
from .relationship_builder import RelationshipBuilder, relationship_builder
from .structured_document_chunker import StructuredDocumentChunker

# 纯文本切块器依赖可选的 langchain-text-splitters；领域检测等核心能力
# 不应因该可选依赖未安装而无法导入。
try:
    from .plain_text_chunker import PlainTextChunkStrategy
except ModuleNotFoundError as exc:
    if exc.name != "langchain_text_splitters":
        raise
    PlainTextChunkStrategy = None

__all__ = [
    'ChunkStrategy',
    'ChunkResult',
    'DomainDetector',
    'domain_detector',
    'DomainChunkerFactory',
    'domain_chunker_factory',
    'GeneralChunker',
    'general_chunker',
    'ASTSanitizer',
    'MetadataInjector',
    'ContextStack',
    'metadata_injector',
    'EntityResolver',
    'entity_resolver',
    'SummaryGenerator',
    'summary_generator',
    'RelationshipBuilder',
    'relationship_builder',
    'StructuredDocumentChunker',
    'PlainTextChunkStrategy',
]
