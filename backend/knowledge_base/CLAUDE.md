# Knowledge Base - 知识库文件

碳排放相关的知识库文档存储目录。

## 用途

存放RAG知识库文档，用于AI问答时的专业问题检索。

## 建议内容

- 碳排放核算国家标准 (GB/T 32151)
- IPCC排放因子数据
- 行业-specific碳排放计算指南
- 填报常见问题解答

## 使用方式

知识库文件会被加载到向量数据库，供RAG检索使用。
具体加载逻辑见 `tantan/backend/rag/knowledge_base.py`。