"""
RAG检索器 - 碳管师收资系统
使用 LangChain LCEL 构建 RAG 管道
"""

from typing import List, Dict, Any, Optional
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from tantan.backend.rag.knowledge_base import get_knowledge_base, CarbonKnowledgeBase
from tantan.backend.rag.langchain_llm import get_langchain_llm, get_langchain_embeddings
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class RAGSearchResult:
    """RAG搜索结果"""

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
            "score": self.score
        }


class RAGSearcher:
    """RAG搜索器 - 使用 LangChain VectorStore"""

    def __init__(
        self,
        knowledge_base: Optional[CarbonKnowledgeBase] = None,
        vectorstore=None
    ):
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self._vectorstore = vectorstore

    @property
    def vectorstore(self):
        """延迟加载 LangChain VectorStore"""
        if self._vectorstore is None:
            from tantan.backend.rag.langchain_vectorstore import create_langchain_vectorstore
            embeddings = get_langchain_embeddings()
            self._vectorstore = create_langchain_vectorstore(embedding=embeddings)
        return self._vectorstore

    def search(self, query: str, top_k: int = 5) -> List[RAGSearchResult]:
        """搜索相关知识"""
        docs = self.vectorstore.similarity_search(query, k=top_k)

        results = []
        for doc in docs:
            results.append(RAGSearchResult(
                chunk_id=doc.metadata.get("chunk_id", ""),
                content=doc.page_content,
                metadata=doc.metadata,
                score=0.0
            ))
        return results

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
        """构建RAG提示词"""
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

        prompt = f"""你是一个碳排放核算的专业助手。请根据以下参考资料回答用户问题。

参考资料：
{context_text}

用户问题：{query}

请结合参考资料给出专业、准确的回答。如果资料中没有相关信息，请说明并提供基于碳排放核算一般知识回答。"""

        return prompt

    def get_topic_related_knowledge(self, topic: str) -> List[Dict[str, Any]]:
        """获取与特定主题相关的所有知识"""
        results = self.search(topic, top_k=10)

        topic_knowledge = []
        for result in results:
            if result.metadata.get("topic") == topic or topic in result.content:
                topic_knowledge.append(result.to_dict())

        return topic_knowledge

    def get_category_knowledge(self, category: str) -> List[Dict[str, Any]]:
        """获取特定类别的所有知识"""
        results = self.search(f"{category}碳排放", top_k=20)

        category_knowledge = []
        for result in results:
            if result.metadata.get("category") == category:
                category_knowledge.append(result.to_dict())

        return category_knowledge


class RAGPipeline:
    """RAG管道 - 使用 LCEL 链整合检索和LLM生成"""

    def __init__(
        self,
        knowledge_base: Optional[CarbonKnowledgeBase] = None,
        llm_client=None,
        vectorstore=None
    ):
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self._llm_client = llm_client
        self._vectorstore = vectorstore
        self._chain = None

    @property
    def llm_client(self):
        """延迟加载 LLM 客户端"""
        if self._llm_client is None:
            self._llm_client = get_langchain_llm()
        return self._llm_client

    @property
    def vectorstore(self):
        """延迟加载 VectorStore"""
        if self._vectorstore is None:
            from tantan.backend.rag.langchain_vectorstore import create_langchain_vectorstore
            from tantan.backend.rag.langchain_llm import get_langchain_embeddings
            embeddings = get_langchain_embeddings()
            self._vectorstore = create_langchain_vectorstore(embedding=embeddings)
        return self._vectorstore

    def _build_chain(self):
        """构建 LCEL RAG 链"""
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})

        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个碳排放核算的专业助手。请根据提供的参考资料给出准确、专业的回答。
如果资料中没有相关信息，请基于碳排放核算一般知识回答。"""),
            ("human", """参考资料：
{context}

用户问题：{question}""")
        ])

        def format_docs(docs):
            """格式化文档列表为字符串"""
            return "\n\n".join([doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in docs])

        # 构建链：retriever 返回文档列表，直接传递给 format_docs
        self._chain = (
            {
                "context": retriever,
                "question": RunnablePassthrough()
            }
            | (lambda x: {"context": format_docs(x["context"]), "question": x["question"]})
            | prompt
            | self.llm_client._llm
            | StrOutputParser()
        )

    def answer(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        include_sources: bool = False
    ) -> Dict[str, Any]:
        """回答问题 - 使用 RAG 检索 + LLM 生成"""
        if self._chain is None:
            self._build_chain()

        try:
            answer = self._chain.invoke(question)

            result = {
                "answer": answer,
                "question": question
            }

            if include_sources:
                # 使用当前实例的 searcher，避免重复创建
                search_results = self.knowledge_base.query(question, top_k=5)
                sources = [
                    {
                        "topic": r.get("metadata", {}).get("topic", "未知"),
                        "source": r.get("metadata", {}).get("source", "未知"),
                        "score": r.get("score", 0)
                    }
                    for r in search_results
                ]
                result["sources"] = sources

            return result

        except Exception as e:
            logger.error(f"RAG管道执行失败: question={question}, error: {str(e)}", exc_info=True)
            return {
                "answer": "抱歉，生成回答时出现错误。",
                "error": str(e)
            }

    def answer_stream(self, question: str, context: Optional[Dict[str, Any]] = None):
        """流式回答问题"""
        if self._chain is None:
            self._build_chain()

        try:
            for chunk in self._chain.stream(question):
                yield chunk
        except Exception as e:
            logger.error(f"RAG流式生成失败: question={question}, error: {str(e)}", exc_info=True)
            yield f"抱歉，生成回答时出现错误：{str(e)}"

    @property
    def _searcher(self) -> RAGSearcher:
        """获取搜索器"""
        return RAGSearcher(vectorstore=self.vectorstore)


# 工厂函数
def get_rag_searcher() -> RAGSearcher:
    """获取RAG搜索器实例"""
    return RAGSearcher()


def get_rag_pipeline() -> RAGPipeline:
    """获取RAG管道实例"""
    return RAGPipeline()