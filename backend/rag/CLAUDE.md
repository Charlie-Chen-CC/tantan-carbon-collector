# RAG - 知识库检索

碳管师收资系统的 RAG（检索增强生成）实现。
**Phase 2.6 起移除 LangChain 三层包装**，直接用 dashscope SDK + 自实现 RAG 管道。

## 核心组件

### LLM 客户端（直接调 dashscope SDK）
- `AliLLMClient` - 同步/流式文本生成（`dashscope.Generation.call`）
- `AliEmbeddingClient` - 文本嵌入（`dashscope.TextEmbedding.call`）
- 工厂函数：`get_llm_client()` / `get_embedding_client()`

### 向量数据库（直连）
- `VectorDBClient` 抽象基类
- `MilvusClient` / `QdrantClient` / `PGVectorClient` 三个实现
- 依赖缺失/连接失败时 **fail-fast**（不再静默 `self._client = None` 静默失效）

### RAG 检索器（手工实现，无 LCEL）
- `RAGSearcher.search(query, top_k)` - 纯检索，返回 `RAGSearchResult` 列表
- `RAGSearcher.build_prompt(query)` - 构造带参考资料的 prompt
- `RAGPipeline.answer(question, context, include_sources=False)` - 检索 + LLM 生成
- `RAGPipeline.answer_stream(question, context)` - 流式版本
- **S3.5 修复**：`search()` 不再有静默 fallback（score=0.0 静默失效）
- `vectorstore` 可选注入，便于测试用 mock

### 知识库管理
- `CarbonKnowledgeBase` - 高级封装，提供 `add_knowledge` / `query` / `retrieve` / `query_with_context`
- `RAGRetriever` - 底层检索器，组合 `AliEmbeddingModel` + `VectorStore`

## API 调用

```python
from tantan.backend.rag import get_rag_pipeline, get_rag_searcher, get_knowledge_base

pipeline = get_rag_pipeline()
result = pipeline.answer(question, context)  # {"answer": ..., "question": ...}

searcher = get_rag_searcher()
results = searcher.search(query, top_k=3)    # List[RAGSearchResult]
```

## 嵌入模型

- 模型: `text-embedding-v2`（配置 `EMBEDDING_MODEL`）
- 维度: 1536（配置 `EMBEDDING_DIM`）

## LLM 模型

- 模型: `qwen-turbo`（配置 `LLM_MODEL`）
- Temperature: 0.7（配置 `LLM_TEMPERATURE`）
- Max Tokens: 2000（配置 `LLM_MAX_TOKENS`）

## 文件提取提示词优化

每个Section的LLM提示词位于 `tantan/backend/agents/file_extractor.py` 的 `SECTION_PROMPTS` 中。

**重要约束：提示词中不得包含硬编码的选项值**，应仅描述业务背景和字段含义，不限制具体取值。

### 提示词结构
```
【业务背景说明】
- 说明该部分数据的业务含义
- 解释数据来源（如HR系统、能源台账等）
- 说明常见的取值范围和格式要求

需要提取的字段：
- 字段1（说明）
- 字段2（说明）

请从提供的原始文本中提取上述字段，以JSON格式返回。只返回JSON。
```

### 优化原则
1. **业务背景**：解释碳排放核算相关概念（如PCF、Scope 2等）
2. **数据来源**：告诉AI可能从哪些文档类型提取
3. **格式说明**：明确取值范围（如是/否、具体单位）
4. **字段优先级**：区分必填字段和可选字段