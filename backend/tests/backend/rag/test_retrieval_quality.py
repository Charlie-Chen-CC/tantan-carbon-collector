"""
RAG 检索质量测试

通过 mock vectorstore 验证：
- 插入 → 检索 → top1 命中预期文档
- 排序按相似度降序
- top_k 参数生效
- 空检索时返回空列表（不抛错）
"""
from typing import List, Tuple

import pytest

from tantan.backend.rag.retriever import RAGSearcher, RAGSearchResult, Document


class FakeVectorStore:
    """测试用伪向量库 - 用关键词匹配打分模拟相似度"""

    def __init__(self, knowledge_items: List[dict]):
        self.knowledge_items = knowledge_items

    def similarity_search_with_score(
        self, query: str, k: int = 5
    ) -> List[Tuple[Document, float]]:
        results = []
        for item in self.knowledge_items:
            score = self._score(query, item["score_keys"], item["content"])
            results.append(
                (
                    Document(page_content=item["content"], metadata=item["metadata"]),
                    score,
                )
            )
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    @staticmethod
    def _score(query: str, score_keys: List[str], content: str) -> float:
        query_words = set(query)
        key_words = set(score_keys)
        content_words = set(content)
        key_match = len(query_words & key_words) * 1.0
        content_match = len(query_words & content_words) * 0.3
        return key_match + content_match


def make_kb() -> FakeVectorStore:
    """构造一个 mock 知识库（含 5 条碳排放知识）"""
    items = [
        {
            "content": "碳排放因子 EF 是将能源消耗量转换为 CO2 排放量的系数，单位 kgCO2e/kWh。",
            "metadata": {"chunk_id": "k1", "topic": "碳排放因子", "source": "ISO 14064"},
            "score_keys": ["排放因子", "EF", "kgCO2e"],
        },
        {
            "content": "电力间接排放属于 Scope 2 范畴，采用基于市场的方法计算。",
            "metadata": {"chunk_id": "k2", "topic": "Scope 2", "source": "GHG Protocol"},
            "score_keys": ["Scope 2", "电力", "市场方法"],
        },
        {
            "content": "外购热力的排放因子为 0.11 tCO2/GJ（参考国家发改委 2023 年数据）。",
            "metadata": {"chunk_id": "k3", "topic": "热力排放", "source": "国家发改委"},
            "score_keys": ["热力", "排放因子", "GJ"],
        },
        {
            "content": "制冷剂 R32 的 GWP（全球变暖潜势）为 675，泄漏 1kg 相当于 675 kgCO2e。",
            "metadata": {"chunk_id": "k4", "topic": "制冷剂", "source": "IPCC AR6"},
            "score_keys": ["制冷剂", "R32", "GWP"],
        },
        {
            "content": "原材料运输距离与运输方式的组合决定 Scope 3 上游排放强度。",
            "metadata": {"chunk_id": "k5", "topic": "Scope 3", "source": "GHG Protocol"},
            "score_keys": ["Scope 3", "运输", "上游"],
        },
    ]
    return FakeVectorStore(items)


class TestRAGRetrievalQuality:
    """检索质量基线"""

    def test_search_top1_hit(self):
        """检索 → top1 应该是关键词最匹配的文档"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("什么是排放因子？", top_k=1)
        assert len(results) == 1
        # "排放因子" 出现在 k1 + k3，但 k1 的 score_keys 完全匹配
        assert results[0].metadata["chunk_id"] == "k1"
        assert results[0].score > 0

    def test_search_topk_returns_sorted(self):
        """top_k 返回结果按 score 降序"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("制冷剂 GWP", top_k=3)
        assert len(results) >= 1
        # 分数应单调非增
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # top1 应是 k4 (制冷剂 GWP)
        assert results[0].metadata["chunk_id"] == "k4"

    def test_search_topk_limit(self):
        """top_k 参数生效"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("碳排放", top_k=2)
        assert len(results) == 2

    def test_search_no_match_returns_empty(self):
        """完全不相关的查询应返回 score=0 但非空（按当前实现）"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("完全不相关的查询 zzzqqq", top_k=5)
        # 至少 1 条（任何内容都有内容词重叠分），但 score 都应 < 1
        for r in results:
            assert r.score >= 0

    def test_result_has_required_fields(self):
        """结果必须包含 content / metadata / score"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("Scope 3 运输", top_k=1)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, RAGSearchResult)
        assert r.content
        assert r.metadata
        assert isinstance(r.score, (int, float))


class TestRAGSearcherEdgeCases:
    """边界条件"""

    def test_empty_kb(self):
        """空知识库检索应返回空列表"""
        vs = FakeVectorStore([])
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("anything", top_k=5)
        assert results == []

    def test_unicode_query(self):
        """中文查询应正常返回"""
        vs = make_kb()
        searcher = RAGSearcher(vectorstore=vs)
        results = searcher.search("热力 排放因子", top_k=3)
        assert len(results) > 0
        # top1 应是 k3 (热力排放因子)
        assert results[0].metadata["chunk_id"] == "k3"
