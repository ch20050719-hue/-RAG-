"""智能家居知识上下文组装器。

保留统一 assemble 接口，所有家居文档采用同一安全、可追溯的上下文格式。
"""

from typing import Dict, List, Optional


class ContextAssembler:
    async def assemble(self, chunks: List[Dict], domain: Optional[str], query: str) -> str:
        if not chunks:
            return ""
        parts = ["<KnowledgeBase type='smart_home'>"]
        for index, chunk in enumerate(chunks, 1):
            source = chunk.get("source") or chunk.get("filename") or "unknown"
            content = str(chunk.get("content", ""))[:800]
            parts.extend([f"[参考内容 {index}]", f"【来源】: {source}", f"【内容】: {content}", ""])
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)


context_assembler = ContextAssembler()
