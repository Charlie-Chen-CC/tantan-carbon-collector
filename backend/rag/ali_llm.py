"""
阿里云 DashScope LLM/Embedding 客户端 - 碳管师收资系统
Phase 2.6：直接用 dashscope SDK，不再走 LangChain 三层包装。

原 LangChain 包装（langchain_llm.py）已删除，逻辑全部内联于此。
"""
import json
from typing import Dict, Any, Optional, List, Iterator, Union

from tantan.backend.config import get_config
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class AliLLMClient:
    """阿里云通义千问 LLM 客户端 - dashscope SDK 直连"""

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

    def _build_call_kwargs(
        self,
        messages: List[Dict[str, str]],
        stream: bool,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        """内部: 构造 dashscope Generation.call 的 kwargs。

        P0-2a 重构: 从原 _call 抽出, async 方法 (achat/achat_stream) 复用。
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "result_format": "message",
        }
        if stream:
            kwargs["stream"] = True
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = self.temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens
        return kwargs

    def _call(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """内部: 调用 dashscope Generation.call。"""
        from dashscope import Generation

        kwargs = self._build_call_kwargs(messages, stream, temperature, max_tokens)

        if stream:
            return self._stream_call(kwargs)
        return self._sync_call(kwargs)

    def _sync_call(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from dashscope import Generation
        try:
            response = Generation.call(**kwargs)
            if response.status_code == 200:
                msg = response.output.choices[0].message
                return {
                    "content": msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", ""),
                    "role": "assistant",
                    "finish_reason": "stop",
                }
            return {"content": "", "error": f"dashscope status {response.status_code}: {response.message}"}
        except Exception as e:
            logger.error(f"dashscope Generation.call 失败: {e}", exc_info=True)
            return {"content": "", "error": str(e)}

    def _stream_call(self, kwargs: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        from dashscope import Generation
        try:
            responses = Generation.call(**kwargs)
            for response in responses:
                if response.status_code == 200:
                    msg = response.output.choices[0].message
                    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                    yield {"content": content, "role": "assistant", "finish_reason": None}
                else:
                    yield {"content": "", "error": f"status {response.status_code}", "finish_reason": "stop"}
        except Exception as e:
            logger.error(f"dashscope 流式生成失败: {e}", exc_info=True)
            yield {"content": "", "error": str(e), "finish_reason": "stop"}

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        **kwargs,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """生成文本"""
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._call(messages, stream=stream, **kwargs)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """对话模式（messages 已是 OpenAI 风格）"""
        normalized = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            normalized.append({"role": role, "content": content})
        return self._call(normalized, stream=stream, **kwargs)

    def count_tokens(self, text: str) -> int:
        """估算 token 数量"""
        return len(text) // 2 + len(text.split())


class AliEmbeddingClient:
    """阿里云文本嵌入客户端 - dashscope SDK 直连"""

    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-embedding/text-embedding"

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = config.EMBEDDING_MODEL
        self.dimension = config.EMBEDDING_DIM

    def encode(self, texts: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        """生成文本嵌入向量"""
        from dashscope import TextEmbedding
        try:
            resp = TextEmbedding.call(
                model=model or self.model,
                input=texts,
                api_key=self.api_key,
            )
            if resp.status_code == 200:
                embeddings = [item["embedding"] for item in resp.output["embeddings"]]
                return {
                    "embeddings": embeddings,
                    "model": model or self.model,
                    "dimension": len(embeddings[0]) if embeddings else 0,
                }
            return {"embeddings": [], "error": f"status {resp.status_code}: {resp.message}"}
        except Exception as e:
            logger.error(f"dashscope TextEmbedding 失败: {e}", exc_info=True)
            return {"embeddings": [], "error": str(e)}

    def encode_single(self, text: str) -> List[float]:
        """单个文本嵌入"""
        result = self.encode([text])
        emb = result.get("embeddings", [])
        return emb[0] if emb else []


# 工厂函数
def get_llm_client() -> AliLLMClient:
    """获取 LLM 客户端实例"""
    return AliLLMClient()


def get_embedding_client() -> AliEmbeddingClient:
    """获取嵌入客户端实例"""
    return AliEmbeddingClient()
