"""智能家居文档切块关系构建器。"""

from dataclasses import replace
from typing import List
from app.chunkers.base_chunker import ChunkResult


class RelationshipBuilder:
    PARENT_RELATION = "PARENT"
    CHILDREN_RELATION = "CHILDREN"
    PREVIOUS_RELATION = "PREVIOUS"
    NEXT_RELATION = "NEXT"
    SOURCE_RELATION = "SOURCE"

    def build(self, chunks: List[ChunkResult], domain: str) -> List[ChunkResult]:
        """为智能家居和通用文档建立顺序及父子关系。"""
        ordered = sorted(chunks, key=lambda item: item.chunk_index)
        result: list[ChunkResult] = []
        for index, chunk in enumerate(ordered):
            relations = dict(chunk.relationships or {})
            if index:
                relations[self.PREVIOUS_RELATION] = ordered[index - 1].chunk_index
            if index < len(ordered) - 1:
                relations[self.NEXT_RELATION] = ordered[index + 1].chunk_index
            result.append(replace(chunk, relationships=relations))
        return result


relationship_builder = RelationshipBuilder()
