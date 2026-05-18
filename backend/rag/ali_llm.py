"""
阿里云LLM客户端 - 碳管师收资系统
接入通义千问系列模型
内部使用 LangChain 进行封装
"""

import json
from typing import Dict, Any, Optional, List, Iterator, Union

from tantan.backend.config import get_config
from tantan.backend.rag.langchain_llm import (
    LangChainLLM,
    LangChainEmbeddings,
    get_langchain_llm,
    get_langchain_embeddings
)
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class AliLLMClient:
    """阿里云通义千问LLM客户端 - 保留原有接口，内部委托LangChain"""

    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

        self._lc_llm = LangChainLLM(api_key=self.api_key, model=self.model)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], Iterator[str]]:
        """
        生成文本

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示
            model: 模型名称（覆盖默认）
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出

        Returns:
            非流式: 包含生成结果的字典
            流式: 生成器yield文本片段
        """
        # 使用 LangChain LLM
        return self._lc_llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def _generate_stream(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> Iterator[str]:
        """流式生成（保留兼容）"""
        return self._lc_llm.generate(prompt=payload.get("input", {}).get("messages", [{"content": ""}])[-1].get("content", ""), stream=True)

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        对话模式

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}] 或支持多模态 [{"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:image/..."}}]}]
            **kwargs: 其他参数

        Returns:
            包含回复的字典
        """
        result = self._lc_llm.chat(messages, stream=False)
        if isinstance(result, dict):
            return result
        return {"content": str(result), "error": None}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应"""
        if "content" in response:
            return {
                "content": response["content"],
                "role": response.get("role", "assistant"),
                "finish_reason": response.get("finish_reason", "stop")
            }
        return {"content": "", "error": response.get("error", "Unknown error")}

    def count_tokens(self, text: str) -> int:
        """估算token数量（简单估算）"""
        return len(text) // 2 + len(text.split())


class AliEmbeddingClient:
    """阿里云文本嵌入客户端 - 保留原有接口，内部委托LangChain"""

    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-embedding/embedding"

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = config.EMBEDDING_MODEL
        self.dimension = config.EMBEDDING_DIM

        self._lc_embeddings = LangChainEmbeddings(api_key=self.api_key, model=self.model)

    def encode(self, texts: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        """
        生成文本嵌入向量

        Args:
            texts: 文本列表
            model: 模型名称（覆盖默认）

        Returns:
            包含嵌入向量的字典
        """
        try:
            embeddings = self._lc_embeddings.encode(texts)
            return {
                "embeddings": embeddings,
                "model": self.model,
                "dimension": len(embeddings[0]) if embeddings else 0
            }
        except Exception as e:
            return {"embeddings": [], "error": str(e)}

    def encode_single(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        return self._lc_embeddings.encode_single(text)

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应"""
        if "embeddings" in response:
            return response
        return {"embeddings": [], "error": response.get("error", "Unknown error")}


# 工厂函数 - 保留向后兼容
def get_llm_client() -> AliLLMClient:
    """获取LLM客户端实例"""
    return AliLLMClient()


def get_embedding_client() -> AliEmbeddingClient:
    """获取嵌入向量客户端实例"""
    return AliEmbeddingClient()