"""
LangChain 兼容层 - 碳管师收资系统
封装 LangChain 的 ChatOpenAI 和 OpenAIEmbeddings 用于 DashScope API
"""

from typing import Dict, Any, Optional, List, Iterator, Union
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from tantan.backend.config import get_config
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class LangChainLLM:
    """LangChain 封装的通义千问 LLM 客户端"""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = model or config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

        self._llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.BASE_URL,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            default_headers={
                "Authorization": f"Bearer {self.api_key}"
            }
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Iterator[str]]:
        """
        生成文本

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示
            stream: 是否流式输出
            **kwargs: 其他参数传递给 LLM

        Returns:
            非流式: 包含生成结果的字典
            流式: 生成器yield文本片段
        """
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        if stream:
            return self._stream_generate(messages, **kwargs)

        response = self._llm.invoke(messages, **kwargs)
        return self._parse_llm_response(response)

    def _stream_generate(self, messages: List[BaseMessage], **kwargs) -> Iterator[str]:
        """流式生成"""
        for chunk in self._llm.stream(messages, **kwargs):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content

    def chat(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Iterator[str]]:
        """
        对话模式

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}] 或 [{"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:image/..."}}]}]
            stream: 是否流式输出

        Returns:
            非流式: 包含回复的字典
            流式: 生成器yield文本片段
        """
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                if isinstance(content, list):
                    # 多模态内容 (含图片)
                    from langchain_core.messages import HumanMessage
                    langchain_messages.append(HumanMessage(content=content))
                else:
                    langchain_messages.append(HumanMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))

        if stream:
            return self._stream_generate(langchain_messages, **kwargs)

        response = self._llm.invoke(langchain_messages, **kwargs)
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response) -> Dict[str, Any]:
        """解析 LangChain LLM 响应"""
        try:
            if hasattr(response, "content"):
                return {
                    "content": response.content,
                    "role": getattr(response, "type", "assistant"),
                    "finish_reason": "stop"
                }
            if hasattr(response, "messages"):
                last_msg = response.messages[-1]
                return {
                    "content": last_msg.content if hasattr(last_msg, "content") else str(last_msg),
                    "role": "assistant",
                    "finish_reason": "stop"
                }
            return {"content": str(response), "error": None}
        except Exception as e:
            logger.error(f"LLM响应解析失败: {str(e)}", exc_info=True)
            return {"content": "", "error": str(e)}

    def count_tokens(self, text: str) -> int:
        """估算token数量（简单估算）"""
        return len(text) // 2 + len(text.split())


class LangChainEmbeddings:
    """LangChain 封装的文本嵌入客户端"""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/text-embedding"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = model or config.EMBEDDING_MODEL
        self.dimension = config.EMBEDDING_DIM

        self._embeddings = OpenAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
            base_url=self.BASE_URL,
            default_headers={
                "Authorization": f"Bearer {self.api_key}"
            }
        )

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        return self._embeddings.embed_documents(texts)

    def encode_single(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        return self._embeddings.embed_query(text)


# 全局实例缓存
_llm_instance: Optional[LangChainLLM] = None
_embeddings_instance: Optional[LangChainEmbeddings] = None


def get_langchain_llm() -> LangChainLLM:
    """获取 LangChain LLM 实例"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LangChainLLM()
    return _llm_instance


def get_langchain_embeddings() -> LangChainEmbeddings:
    """获取 LangChain Embeddings 实例"""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = LangChainEmbeddings()
    return _embeddings_instance