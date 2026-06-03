"""
RAG 检索器 - 碳管师收资系统
Phase 2.6：移除 LangChain LCEL 包装，直接用 ali_llm + knowledge_base 实现 RAG 管道。

S3.5 修复：search() 不再有静默 fallback（score=0.0 静默失效），
若 vectorstore 不支持带分数搜索，直接抛错。
"""
from typing import List, Dict, Any, Optional, Union, Iterator

from tantan.backend.rag.ali_llm import get_llm_client
from tantan.backend.rag.knowledge_base import get_knowledge_base, CarbonKnowledgeBase
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


# 简易 Document 替代 langchain_core.documents.Document
class Document:
    """文档片段 - 与 LangChain Document 接口兼容（page_content / metadata）"""

    def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class RAGSearchResult:
    """RAG 搜索结果"""

    def __init__(self, chunk_id: str, content: str, metadata: Dict[str, Any], score: float):
        self.chunk_id = chunk_id
        self.content = content
        self.metadata = metadata
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
        }


class RAGSearcher:
    """RAG 搜索器 - 直接对接 knowledge_base / 自定义 vectorstore"""

    def __init__(
        self,
        knowledge_base: Optional[CarbonKnowledgeBase] = None,
        vectorstore=None,
    ):
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self._vectorstore = vectorstore

    @property
    def vectorstore(self):
        """延迟加载 vectorstore - 默认包装 knowledge_base.retrieve()"""
        if self._vectorstore is None:
            self._vectorstore = _KnowledgeBaseVectorStoreAdapter(self.knowledge_base)
        return self._vectorstore

    def search(self, query: str, top_k: int = 5) -> List[RAGSearchResult]:
        """搜索相关知识

        S3.5：vectorstore 不支持 similarity_search_with_score 时直接抛错，不静默 fallback。
        """
        docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=top_k)
        return [
            RAGSearchResult(
                chunk_id=doc.metadata.get("chunk_id", ""),
                content=doc.page_content,
                metadata=doc.metadata,
                score=score,
            )
            for doc, score in docs_with_scores
        ]

    def search_with_context(self, query: str, context: Optional[Dict[str, Any]] = None, top_k: int = 3) -> str:
        """带上下文的搜索，返回格式化文本"""
        results = self.search(query, top_k)
        if not results:
            return "抱歉，没有找到相关信息。"

        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[参考资料{i}]\n"
                f"主题：{result.metadata.get('topic', '未知')}\n"
                f"内容：{result.content}"
            )
        return "\n\n".join(context_parts)

    def build_prompt(self, query: str, context: Optional[Dict[str, Any]] = None, top_k: int = 3) -> str:
        """构建 RAG 提示词"""
        search_results = self.search(query, top_k)
        if not search_results:
            return f"问题：{query}\n\n没有找到相关背景知识，请根据一般性碳排放核算知识回答。"

        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[参考资料{i}]（相关度：{result.score:.2f}）\n"
                f"主题：{result.metadata.get('topic', '未知')}\n"
                f"来源：{result.metadata.get('source', '未知')}\n"
                f"内容：{result.content}"
            )

        context_text = "\n\n".join(context_parts)
        return f"""你是一个碳排放核算的专业助手。请根据以下参考资料回答用户问题。

参考资料：
{context_text}

用户问题：{query}

请结合参考资料给出专业、准确的回答。如果资料中没有相关信息，请说明并提供基于碳排放核算一般知识回答。"""

    def get_topic_related_knowledge(self, topic: str) -> List[Dict[str, Any]]:
        results = self.search(topic, top_k=10)
        return [r.to_dict() for r in results if r.metadata.get("topic") == topic or topic in r.content]

    def get_category_knowledge(self, category: str) -> List[Dict[str, Any]]:
        results = self.search(f"{category}碳排放", top_k=20)
        return [r.to_dict() for r in results if r.metadata.get("category") == category]


class _KnowledgeBaseVectorStoreAdapter:
    """把 knowledge_base 包装成具有 LangChain 兼容接口的 vectorstore

    提供 similarity_search_with_score，让 RAGSearcher 可选注入。
    """

    def __init__(self, knowledge_base: CarbonKnowledgeBase):
        self.knowledge_base = knowledge_base

    def similarity_search_with_score(self, query: str, k: int = 5) -> List[tuple[Document, float]]:
        """调 knowledge_base.retrieve()，返回 (Document, score) 列表"""
        raw = self.knowledge_base.retrieve(query, top_k=k)
        return [
            (Document(page_content=r.get("content", ""), metadata=r.get("metadata", {})), r.get("score", 0.0))
            for r in raw
        ]


class RAGPipeline:
    """RAG 管道 - 手工实现检索 + LLM 生成（不再用 LCEL 链）"""

    SYSTEM_PROMPT = """你是一个碳排放核算的专业助手。请根据提供的参考资料给出准确、专业的回答。
如果资料中没有相关信息，请基于碳排放核算一般知识回答。"""

    def __init__(
        self,
        knowledge_base: Optional[CarbonKnowledgeBase] = None,
        llm_client=None,
        vectorstore=None,
    ):
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self._llm_client = llm_client
        self._vectorstore = vectorstore
        self._searcher: Optional[RAGSearcher] = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    @property
    def searcher(self) -> RAGSearcher:
        if self._searcher is None:
            self._searcher = RAGSearcher(
                knowledge_base=self.knowledge_base,
                vectorstore=self._vectorstore,
            )
        return self._searcher

    def _retrieve(self, question: str, top_k: int = 5) -> List[RAGSearchResult]:
        return self.searcher.search(question, top_k=top_k)

    def _build_prompt(self, question: str, results: List[RAGSearchResult]) -> str:
        if not results:
            context_text = "（无相关参考资料）"
        else:
            context_text = "\n\n".join(
                f"[参考资料{i + 1}]\n{r.content}" for i, r in enumerate(results)
            )
        return f"""参考资料：
{context_text}

用户问题：{question}"""

    def answer(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        include_sources: bool = False,
    ) -> Dict[str, Any]:
        """回答问题 - 检索 + LLM 生成"""
        try:
            results = self._retrieve(question, top_k=5)
            prompt = self._build_prompt(question, results)
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            resp = self.llm_client.chat(messages)
            answer_text = resp.get("content", "") if isinstance(resp, dict) else str(resp)

            result: Dict[str, Any] = {"answer": answer_text, "question": question}
            if include_sources:
                result["sources"] = [
                    {
                        "topic": r.metadata.get("topic", "未知"),
                        "source": r.metadata.get("source", "未知"),
                        "score": r.score,
                    }
                    for r in results
                ]
            return result
        except Exception as e:
            logger.error(f"RAG 管道执行失败: question={question}, error: {e}", exc_info=True)
            return {"answer": "抱歉，生成回答时出现错误。", "error": str(e), "question": question}

    def answer_stream(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        """流式回答"""
        try:
            results = self._retrieve(question, top_k=5)
            prompt = self._build_prompt(question, results)
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            stream = self.llm_client.chat(messages, stream=True)
            for chunk in stream:
                if isinstance(chunk, dict):
                    yield chunk.get("content", "")
                else:
                    yield str(chunk)
        except Exception as e:
            logger.error(f"RAG 流式生成失败: question={question}, error: {e}", exc_info=True)
            yield f"抱歉，生成回答时出现错误：{e}"


# 工厂函数
def get_rag_searcher() -> RAGSearcher:
    return RAGSearcher()


def get_rag_pipeline() -> RAGPipeline:
    return RAGPipeline()
