"""
RAG 检索器测试 - 验证 S3.5 修复

关键断言：
- RAGSearcher.search() 不再有静默 fallback（score=0.0 静默失效）
- 若 vectorstore 不支持 similarity_search_with_score，应直接抛错（不返回假数据）
- RAGSearchResult.score 必须来自 vectorstore 的真实打分
"""
from unittest.mock import MagicMock

import pytest

from tantan.backend.rag.retriever import RAGSearcher, RAGSearchResult, Document


class TestRAGSearcherNoSilentFallback:
    """S3.5 修复：RAGSearcher.search 不再有 except 静默 fallback"""

    def _make_searcher(self, vs_mock) -> RAGSearcher:
        s = RAGSearcher(knowledge_base=MagicMock(), vectorstore=vs_mock)
        return s

    def test_search_uses_real_score(self):
        """vectorstore 正常返回 score 时，result.score 必须来自 vs"""
        vs = MagicMock()
        vs.similarity_search_with_score.return_value = [
            (Document(page_content="doc1", metadata={"chunk_id": "c1"}), 0.92),
            (Document(page_content="doc2", metadata={"chunk_id": "c2"}), 0.78),
        ]
        s = self._make_searcher(vs)
        results = s.search("query", top_k=2)

        assert len(results) == 2
        assert results[0].score == 0.92
        assert results[1].score == 0.78
        assert results[0].content == "doc1"
        assert results[0].chunk_id == "c1"
        vs.similarity_search_with_score.assert_called_once_with("query", k=2)
        # 关键：未调用无分数版本
        vs.similarity_search.assert_not_called()

    def test_search_fails_fast_when_vs_lacks_scored_api(self):
        """vectorstore 不支持 similarity_search_with_score 时直接抛错（不再 fallback score=0.0）"""
        vs = MagicMock()
        vs.similarity_search_with_score.side_effect = AttributeError("not supported")
        s = self._make_searcher(vs)

        with pytest.raises(AttributeError):
            s.search("query", top_k=3)
        # 静默 fallback 已移除，不会再调用不带分数的版本
        vs.similarity_search.assert_not_called()

    def test_search_propagates_runtime_errors(self):
        """DB 连不上等运行时错误应直接冒泡，不被吞掉"""
        vs = MagicMock()
        vs.similarity_search_with_score.side_effect = ConnectionError("PG down")
        s = self._make_searcher(vs)

        with pytest.raises(ConnectionError, match="PG down"):
            s.search("query", top_k=5)


class TestRAGSearchResultShape:
    """RAGSearchResult 数据类契约"""

    def test_to_dict_preserves_score(self):
        r = RAGSearchResult(chunk_id="x", content="c", metadata={"k": "v"}, score=0.55)
        d = r.to_dict()
        assert d == {"chunk_id": "x", "content": "c", "metadata": {"k": "v"}, "score": 0.55}
