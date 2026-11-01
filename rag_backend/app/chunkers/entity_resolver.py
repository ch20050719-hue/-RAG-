"""智能家居文档实体解析器。

智能家居知识通常使用设备 ID 和场景名；此兼容入口仅复制元数据，避免改变原文内容。
"""

from dataclasses import replace
from typing import List

from app.chunkers.base_chunker import ChunkResult
from app.models.structured_document import StructuredDocument


class EntityResolver:
    async def resolve(self, structured_doc: StructuredDocument, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """保留切块内容并标记来源，返回新的 ChunkResult 对象。"""
        return [replace(chunk, metadata={**(chunk.metadata or {}), "entity_resolution": "smart_home"}) for chunk in chunks]


entity_resolver = EntityResolver()
