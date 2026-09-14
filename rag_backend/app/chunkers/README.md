# Chunkers（领域感知分块体系）

把解析器输出的结构化文档（`ParsedDocument`）切分为带元数据与关系的 chunk。核心思路：**不同领域的专业文档用不同的切分策略**，由领域检测器自动路由。

## 处理管线

```
ParsedDocument
   │
   ▼
DomainDetector 三级路由（domain_detector.py）
   ① 用户显式指定 kb_category（smart_home/general）
   ② 文件名关键词启发（FILENAME_PATTERNS）
   ③ LLM 单 token 分类（取正文前 800 字，prompts/chunkers/domain_classify_prompt.md）
   │
   ▼
DomainChunkerFactory（懒加载缓存）→ 领域分块器
   │
   ▼
管道组件：ASTSanitizer → MetadataInjector → (EntityResolver) → (SummaryGenerator) → RelationshipBuilder
```

## 分块器清单

| 类 | 文件 | 领域/格式 | 核心策略 |
|---|---|---|---|
| `GeneralChunker` | general_chunker.py | 智能家居与通用知识 | 保留结构化段落、表格和标题上下文，支持父子节点 |
| `GeneralChunker` | general_chunker.py | 通用文档 | Auto-Merging 双粒度：先切 PARENT（1024 token）再按句切 LEAF（256 token），互置 PARENT/CHILDREN 关系 |
| `AdaptiveChunker` | adaptive_chunker.py | 兜底/语义 | 双模式：LLM 语义边界 JSON / 纯规则（Markdown 标题、第X章/节、双换行），合并到 200~1000 字符 |
| `PropositionChunker` | adaptive_chunker.py | 事实密集型 | 每 2000 字一段调 LLM 提取原子命题（fact/rule） |
| `StructuredDocumentChunker` | structured_document_chunker.py | 结构化通用 | 章节树 DFS + token 驱动合并；超长先断句再截断；20% 阈值合并小块 |
| `MarkdownChunkStrategy` | markdown_chunker.py | Markdown | 标题栈解析（#~######），按 token 合并段落，末尾逆序取 overlap |
| `PlainTextChunkStrategy` | plain_text_chunker.py | 纯文本/CSV | LangChain RecursiveCharacterTextSplitter（字符数计） |

## 管道组件

| 组件 | 文件 | 职责 |
|---|---|---|
| `ASTSanitizer` | ast_sanitizer.py | 过滤伪标题（>50 字符或 >15 词），修复层级跳跃（H1→H3 自动补隐式 H2） |
| `MetadataInjector` + `ContextStack` | metadata_injector.py | DFS 标题树，按层级继承注入年份/季度/报表类型/公司名/货币等 6 类正则元数据 |
| `EntityResolver` | entity_resolver.py | 家居实体元数据解析兼容入口 |
| `SummaryGenerator` | summary_generator.py | 家居知识 PARENT 节点摘要 |
| `RelationshipBuilder` | relationship_builder.py | 按 domain 单遍构建 PARENT/CHILDREN/PREVIOUS/NEXT/SOURCE 关系 |

## 关系类型与检索的配合

- PARENT/CHILD：检索命中 LEAF 时可向上展开父块补充上下文（`unified_retriever` 的 Auto-Merging 仅在 general 域启用）。
- PREVIOUS/NEXT：知识段落的前后顺序链，支持上下文连续展开。
- 表格原子块：保证设备参数表在检索结果中完整呈现，不被截断。

## 测试

```bash
pytest tests/unit/test_adaptive_chunker.py
pytest tests/integration/test_chunk_integration.py
```
