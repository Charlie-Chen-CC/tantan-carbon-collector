# RAG - 知识库检索

基于LangChain的RAG（检索增强生成）实现。

## 核心组件

### LangChain LLM封装
- `LangChainLLM` - 封装ChatOpenAI，适配DashScope API
- `LangChainEmbeddings` - 封装OpenAIEmbeddings，适配DashScope

### 向量数据库适配
- `LangChainVectorStore` - 桥接现有VectorDBClient到LangChain VectorStore接口
- 支持: pgvector, Milvus, Qdrant

### RAG管道
```python
RAGPipeline = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

### 知识库检索器
- `RAGPipeline.answer()` - 带上下文的问答
- `RAGSearcher.search()` - 纯检索模式

## API调用

```python
from tantan.backend.rag import get_rag_pipeline, get_rag_searcher

pipeline = get_rag_pipeline()
result = pipeline.answer(question, context)

searcher = get_rag_searcher()
results = searcher.search(query, top_k=3)
```

## 嵌入模型

- 模型: `text-embedding-v2`
- 维度: 1536
- API Base: `https://dashscope.aliyuncs.com/compatible-mode/text-embedding`

## LLM模型

- 模型: `qwen-turbo`
- Temperature: 0.7
- Max Tokens: 2000
- API Base: `https://dashscope.aliyuncs.com/compatible-mode/v1`