"""
RAG检索模块 - 碳管师收资系统
使用阿里云embedding和向量数据库存储和检索碳排放相关知识
"""

import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from tantan.backend.config import get_config
from tantan.backend.rag.vector_db import VectorDBClient, VectorDBFactory
from tantan.backend.rag.ali_llm import AliEmbeddingClient, get_embedding_client
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class EmbeddingModel(ABC):
    """Embedding模型抽象类"""

    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本编码为向量"""
        pass


class AliEmbeddingModel(EmbeddingModel):
    """阿里云embedding模型"""

    def __init__(self, embedding_client: Optional[AliEmbeddingClient] = None):
        self.embedding_client = embedding_client or get_embedding_client()
        self.dimension = get_config().EMBEDDING_DIM

    def encode(self, texts: List[str]) -> List[List[float]]:
        """使用阿里云embedding API编码文本"""
        result = self.embedding_client.encode(texts)

        if "embeddings" in result and result["embeddings"]:
            return result["embeddings"]

        raise ValueError(f"Failed to encode texts: {result}")


class VectorStore:
    """向量存储"""

    def __init__(self, vector_db_client: Optional[VectorDBClient] = None):
        self.vector_db_client = vector_db_client or VectorDBFactory.create_client()
        self.collection_name = get_config().MILVUS_COLLECTION if get_config().VECTOR_DB_TYPE == "milvus" else get_config().QDRANT_COLLECTION
        self.dimension = get_config().EMBEDDING_DIM

    def connect(self) -> bool:
        """连接向量数据库"""
        return self.vector_db_client.connect()

    def disconnect(self) -> None:
        """断开向量数据库连接"""
        self.vector_db_client.disconnect()

    def init_collection(self, force_recreate: bool = False) -> bool:
        """初始化集合

        Args:
            force_recreate: 是否强制重建集合（会删除现有数据）
        """
        try:
            if force_recreate:
                # 只有明确要求时才删除现有集合
                try:
                    self.vector_db_client.delete_collection(self.collection_name)
                except Exception:
                    pass  # 集合不存在时忽略

            return self.vector_db_client.create_collection(
                self.collection_name,
                self.dimension,
                {"description": "Carbon knowledge base"}
            )
        except Exception as e:
            # 如果集合已存在，create_collection 会失败，这是正常行为
            logger.error(f"初始化集合失败: collection={self.collection_name}, error: {str(e)}", exc_info=True)
            return False

    def add(self, doc_id: str, vector: List[float], document: Dict[str, Any]) -> bool:
        """添加文档"""
        try:
            self.vector_db_client.insert(
                self.collection_name,
                [vector],
                [document],
                [doc_id]
            )
            return True
        except Exception as e:
            logger.error(f"添加文档失败: error: {str(e)}", exc_info=True)
            return False

    def add_batch(self, vectors: List[List[float]], documents: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """批量添加文档"""
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            self.vector_db_client.insert(
                self.collection_name,
                vectors,
                documents,
                ids
            )
            return ids
        except Exception as e:
            logger.error(f"批量添加文档失败: count={len(documents)}, error: {str(e)}", exc_info=True)
            return []

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索最相似的文档"""
        try:
            results = self.vector_db_client.search(
                self.collection_name,
                query_vector,
                top_k
            )
            return results
        except Exception as e:
            logger.error(f"搜索失败: query={query}, error: {str(e)}", exc_info=True)
            return []

    def delete(self, doc_id: str) -> bool:
        """删除文档"""
        try:
            return self.vector_db_client.delete(self.collection_name, [doc_id])
        except Exception as e:
            logger.error(f"删除文档失败: doc_id={doc_id}, error: {str(e)}", exc_info=True)
            return False

    def count(self) -> int:
        """文档数量"""
        # 简化实现
        return 0


class KnowledgeChunk:
    """知识块"""

    def __init__(self, chunk_id: str, content: str, metadata: Dict[str, Any]):
        self.chunk_id = chunk_id
        self.content = content
        self.metadata = metadata
        self.created_at = datetime.now()
        self.accessed_at = datetime.now()
        self.access_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count
        }


class RAGRetriever:
    """RAG检索器"""

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.embedding_model = embedding_model or AliEmbeddingModel()
        self.vector_store = vector_store or VectorStore()
        self.chunks: Dict[str, KnowledgeChunk] = {}
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """确保已初始化"""
        if self._initialized:
            return True

        # 连接向量数据库
        if not self.vector_store.connect():
            logger.error(f"连接向量数据库失败", exc_info=True)
            return False

        # 尝试创建集合
        self.vector_store.init_collection()
        self._initialized = True
        return True

    def add_knowledge(self, content: str, metadata: Dict[str, Any]) -> str:
        """添加知识"""
        if not self._ensure_initialized():
            return ""

        chunk_id = str(uuid.uuid4())

        # 创建知识块
        chunk = KnowledgeChunk(chunk_id, content, metadata)
        self.chunks[chunk_id] = chunk

        # 计算向量并存储
        try:
            vectors = self.embedding_model.encode([content])
            vector = vectors[0]

            self.vector_store.add(chunk_id, vector, chunk.to_dict())
        except Exception as e:
            logger.error(f"添加知识失败: error: {str(e)}", exc_info=True)

        return chunk_id

    def add_knowledge_batch(self, knowledge_list: List[Dict[str, Any]]) -> List[str]:
        """批量添加知识"""
        if not self._ensure_initialized():
            return []

        chunk_ids = []
        contents = []
        documents = []

        # 准备数据
        for item in knowledge_list:
            chunk_id = str(uuid.uuid4())
            chunk = KnowledgeChunk(chunk_id, item["content"], item.get("metadata", {}))
            self.chunks[chunk_id] = chunk

            chunk_ids.append(chunk_id)
            contents.append(item["content"])
            documents.append(chunk.to_dict())

        # 批量编码
        try:
            vectors = self.embedding_model.encode(contents)
            self.vector_store.add_batch(vectors, documents, chunk_ids)
        except Exception as e:
            logger.error(f"批量添加知识失败: count={len(chunks)}, error: {str(e)}", exc_info=True)

        return chunk_ids

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索知识"""
        if not self._ensure_initialized():
            return []

        try:
            # 计算查询向量
            vectors = self.embedding_model.encode([query])
            query_vector = vectors[0]

            # 搜索
            results = self.vector_store.search(query_vector, top_k)

            # 更新访问记录
            for result in results:
                chunk_id = result.get("id", "")
                if chunk_id in self.chunks:
                    chunk = self.chunks[chunk_id]
                    chunk.accessed_at = datetime.now()
                    chunk.access_count += 1

            return results

        except Exception as e:
            logger.error(f"检索知识失败: query={query}, error: {str(e)}", exc_info=True)
            return []

    def retrieve_with_rerank(self, query: str, top_k: int = 5, rerank_top: int = 3) -> List[Dict[str, Any]]:
        """带重排序的检索"""
        # 初步检索
        results = self.retrieve(query, top_k * 2)

        # 简单重排序：基于相关性
        reranked = []
        for result in results:
            document = result.get("document", {})
            metadata = document.get("metadata", {})
            score = result.get("score", 0)

            # 综合分数
            final_score = score
            result["final_score"] = final_score
            reranked.append(result)

        # 排序并返回top_k
        reranked.sort(key=lambda x: x["final_score"], reverse=True)
        return reranked[:rerank_top]

    def get_knowledge_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取知识"""
        if chunk_id in self.chunks:
            chunk = self.chunks[chunk_id]
            chunk.accessed_at = datetime.now()
            chunk.access_count += 1
            return chunk.to_dict()
        return None

    def delete_knowledge(self, chunk_id: str) -> bool:
        """删除知识"""
        if chunk_id in self.chunks:
            del self.chunks[chunk_id]
            return self.vector_store.delete(chunk_id)
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_access = sum(chunk.access_count for chunk in self.chunks.values())
        return {
            "total_chunks": len(self.chunks),
            "total_access": total_access
        }


class CarbonKnowledgeBase:
    """碳排放专业知识库"""

    def __init__(self):
        self.retriever: Optional[RAGRetriever] = None
        self._initialized = False

    def _get_retriever(self) -> RAGRetriever:
        """获取或创建检索器"""
        if self.retriever is None:
            self.retriever = RAGRetriever()
        return self.retriever

    def initialize(self) -> bool:
        """初始化知识库"""
        if self._initialized:
            return True

        retriever = self._get_retriever()
        if not retriever._ensure_initialized():
            return False

        # 初始化知识
        self._initialize_knowledge()
        self._initialized = True
        return True

    def _initialize_knowledge(self):
        """初始化碳排放知识库"""
        knowledge_items = [
            # 基本概念
            {
                "content": "碳排放核算是对温室气体排放进行量化的过程，包括直接排放（范围1）和间接排放（范围2）。核算边界应覆盖组织拥有或控制的所有排放源。",
                "metadata": {"topic": "碳核算基本概念", "category": "基础", "source": "GB/T 32150"}
            },
            {
                "content": "范围1排放是指企业拥有或控制的排放源产生的直接温室气体排放，主要包括：固定源燃烧（如锅炉、发电机）、移动源燃烧（如公司车辆）、逸散排放（如制冷剂泄漏）、过程排放（如工业过程）",
                "metadata": {"topic": "范围1排放", "category": "基础", "source": "GHG Protocol"}
            },
            {
                "content": "范围2排放是指企业外购电力、热力、蒸汽产生的间接温室气体排放。这些排放发生在生产这些能源的地点，但由企业消费这些能源而产生。范围2核算需要使用基于位置或基于市场的排放因子。",
                "metadata": {"topic": "范围2排放", "category": "基础", "source": "GHG Protocol"}
            },
            {
                "content": "碳排放因子是将活动水平数据转换为温室气体排放量的系数。常用单位包括kgCO2e/kWh（电力）、kgCO2e/t（燃料）。数据来源应权威可靠，如IPCC、GB/T 32151、生态环境部公告等。",
                "metadata": {"topic": "碳排放因子", "category": "因子", "source": "IPCC"}
            },
            {
                "content": "活动水平数据是指导致温室气体排放的活动数量，如燃料消耗量（吨）、电力消耗量（kWh）、蒸汽消耗量（t）等。活动水平数据应来源可靠，优先使用计量设备数据，其次使用估算数据。",
                "metadata": {"topic": "活动水平数据", "category": "基础", "source": "GB/T 32150"}
            },

            # 范围1排放详细说明
            {
                "content": "固定燃烧源排放主要来自锅炉、窑炉、发电机等设备。计算方法：燃料消耗量 × 排放因子 × 氧化率。常用燃料包括天然气、煤炭、柴油、重油等。排放因子应使用低位发热值计算。",
                "metadata": {"topic": "固定燃烧源排放", "category": "范围1", "source": "GB/T 32151.10"}
            },
            {
                "content": "移动源燃烧排放主要来自公司自有车辆，包括商务车、叉车、工程机械等。计算方法：燃料消耗量 × 排放因子。车辆排放应使用行驶里程和平均燃油消耗量法核算。",
                "metadata": {"topic": "移动源燃烧排放", "category": "范围1", "source": "IPCC"}
            },
            {
                "content": "逸散排放主要包括：制冷剂泄漏（空调、冷冻机）、CO2灭火器使用、废水厌氧处理甲烷逸散、化粪池甲烷等。逸散排放计算需要使用年全球变暖潜能值（GWP）。",
                "metadata": {"topic": "逸散排放", "category": "范围1", "source": "IPCC AR6"}
            },
            {
                "content": "制冷剂排放计算公式：制冷剂填充量(kg) × 泄漏率 × GWP值。常用制冷剂包括R410A（RWP=2088）、R134A（GWP=1430）、R32（GWP=675）、R22（GWP=1810）等。新填充量应记录初始填充量和补充量。",
                "metadata": {"topic": "制冷剂排放", "category": "范围1", "source": "IPCC AR6"}
            },
            {
                "content": "废水厌氧处理甲烷逸散量计算：废水排放量(m3) × BOD浓度(kg/m3) × 甲烷转化因子(MCF) × BOD去除率 × 16/12（甲烷碳含量）。MCF值取决于厌氧工艺类型。",
                "metadata": {"topic": "废水处理排放", "category": "范围1", "source": "IPCC 2006"}
            },

            # 范围2排放详细说明
            {
                "content": "外购电力排放计算：外购电量(kWh) × 电力排放因子(kgCO2e/kWh)。电网排放因子应使用生态环境部发布的区域电网基准线排放因子或企业实际排放因子。",
                "metadata": {"topic": "外购电力排放", "category": "范围2", "source": "生态环境部公告"}
            },
            {
                "content": "外购热力（蒸汽）排放计算：外购蒸汽量(t) × 热力排放因子(kgCO2e/t)。蒸汽排放因子与燃料类型相关，燃煤锅炉蒸汽排放因子约为240kgCO2e/t，燃气锅炉约为200kgCO2e/t。",
                "metadata": {"topic": "外购热力排放", "category": "范围2", "source": "GB/T 32151.10"}
            },
            {
                "content": "绿色电力证书（绿证）是企业购买可再生能源电力的凭证。国内绿证（GEC）由国家可再生能源信息管理中心发行，国际绿证（I-REC、TIGR）由国际机构发行。购买绿证可抵扣外购电力的碳排放量。",
                "metadata": {"topic": "绿色电力证书", "category": "范围2", "source": "政策文件"}
            },
            {
                "content": "碳排放权交易（ETS）是指在碳市场进行碳配额（CEA）或中国自愿减排量（CCER）买卖的交易行为。碳配额由政府免费分配或拍卖发放，CCER通过项目减排量获得。",
                "metadata": {"topic": "碳排放权交易", "category": "政策", "source": "碳交易管理办法"}
            },

            # 燃料使用
            {
                "content": "燃料燃烧排放计算统一公式：燃料消耗量 × 应用基低位发热量(MJ/kg或MJ/Nm3) × 排放因子(kgCO2e/GJ) / 1000。不同燃料的排放因子不同，天然气约56kgCO2e/GJ，煤炭约95kgCO2e/GJ。",
                "metadata": {"topic": "燃料燃烧排放计算", "category": "计算方法", "source": "GB/T 32151"}
            },
            {
                "content": "天然气包括管道天然气、液化天然气(LNG)、压缩天然气(CNG)。天然气主要成分为甲烷，热值约为36MJ/Nm3，排放因子约为56kgCO2e/GJ（按能量单位）。",
                "metadata": {"topic": "天然气参数", "category": "燃料", "source": "GB/T 2589"}
            },
            {
                "content": "煤炭按挥发分含量分为无烟煤、烟煤、褐煤等。煤炭排放因子与其碳含量相关，约为95-100kgCO2e/GJ。使用时应采用收到基低位发热量计算。",
                "metadata": {"topic": "煤炭参数", "category": "燃料", "source": "GB/T 2589"}
            },
            {
                "content": "柴油和重油是石油炼制产品。柴油主要用于车辆和发电机，排放因子约为68kgCO2e/GJ。重油用于锅炉和窑炉，排放因子约为75kgCO2e/GJ。",
                "metadata": {"topic": "石油类产品参数", "category": "燃料", "source": "GB/T 2589"}
            },

            # 电力和热力
            {
                "content": "电力消耗统计应区分全厂用电、生产用电、办公用电、目标产品产线用电等单元。可单独计量的单元应优先使用计量表数据，不可单独统计的可使用分摊方法估算。",
                "metadata": {"topic": "电力消耗统计", "category": "电力热力", "source": "GB/T 32150"}
            },
            {
                "content": "光伏发电是企业自建可再生能源发电设施的主要形式。自发自用模式可抵扣外购电力，上网出售模式则不能抵扣但可获得发电收入。绿色权益归属应在投资建设前明确约定。",
                "metadata": {"topic": "光伏发电", "category": "可再生能源", "source": "政策文件"}
            },
            {
                "content": "蒸汽参数包括蒸汽温度和压力。不同压力等级的蒸汽适用于不同工艺需求。蒸汽消耗量应使用流量计计量，蒸汽热值应根据温度压力换算。",
                "metadata": {"topic": "蒸汽参数", "category": "电力热力", "source": "工艺手册"}
            },

            # 三废处理
            {
                "content": "废水处理方式包括厂内处理和委托外部处理。厂内有废水处理设施时，应区分有氧处理和厌氧处理工艺。厌氧处理会产生甲烷逸散，需要计入范围1排放。",
                "metadata": {"topic": "废水处理方式", "category": "三废处理", "source": "GB/T 32151.6"}
            },
            {
                "content": "废气处理方式包括RTO/RCO焚烧、活性炭吸附、湿法除尘等。RTO（蓄热式燃烧）适用于高浓度有机废气，处理效率可达99%以上。活性炭吸附适用于低浓度大风量废气。",
                "metadata": {"topic": "废气处理方式", "category": "三废处理", "source": "环保手册"}
            },
            {
                "content": "危险废物处理方式包括委外焚烧、资源化和自行处理。委外焚烧应选择有资质的处置单位。自行焚烧需要控制污染物排放。资源化利用可抵扣部分碳排放。",
                "metadata": {"topic": "危废处理", "category": "三废处理", "source": "固废法"}
            },

            # 产品碳足迹
            {
                "content": "产品碳足迹（PCF）是指产品整个生命周期中的温室气体排放量。生命周期阶段包括原材料获取、生产制造、运输配送、使用阶段、废弃处置等。",
                "metadata": {"topic": "产品碳足迹", "category": "产品", "source": "ISO 14067"}
            },
            {
                "content": "产品碳足迹核算应明确核算边界和系统边界。系统边界定义哪些过程纳入核算。分配方法包括物理分配和经济分配。单位碳足迹（tCO2e/t或tCO2e/件）用于产品比较。",
                "metadata": {"topic": "PCF核算方法", "category": "产品", "source": "PAS 2050"}
            },
            {
                "content": "生产过程排放包括主要工艺过程排放和辅助工艺排放。主要原材料和辅料的碳排放应追溯到上游。电力和蒸汽消耗应使用适当分配因子分摊到各产品。",
                "metadata": {"topic": "生产过程排放", "category": "产品", "source": "GB/T 32150"}
            },

            # 碳排放因子表
            {
                "content": "常用电力排放因子：华东电网0.5815kgCO2e/kWh、华北电网0.5923kgCO2e/kWh、东北电网0.5572kgCO2e/kWh、西北电网0.6671kgCO2e/kWh。因子值每年更新。",
                "metadata": {"topic": "电网排放因子", "category": "因子", "source": "生态环境部公告"}
            },
            {
                "content": "常用燃料排放因子：天然气56.2kgCO2e/GJ、液化石油气61.4kgCO2e/GJ、柴油68.4kgCO2e/GJ、煤炭95.0kgCO2e/GJ、重油77.4kgCO2e/GJ。",
                "metadata": {"topic": "燃料排放因子", "category": "因子", "source": "GB/T 32151"}
            },
            {
                "content": "制冷剂GWP值：R410A=2088、R134a=1430、R32=675、R22=1810、R404A=3944、R507A=3985、R290=0.0002（丙烷，几乎无GWP）。GWP值来源于IPCC AR6。",
                "metadata": {"topic": "制冷剂GWP值", "category": "因子", "source": "IPCC AR6"}
            },

            # 数据质量
            {
                "content": "碳排放数据质量控制应遵循：完整性（覆盖所有排放源）、一致性（计算方法统一）、准确性（数据来源可靠）、透明性（计算过程可追溯）。",
                "metadata": {"topic": "数据质量控制", "category": "质量管理", "source": "GHG Protocol"}
            },
            {
                "content": "不确定性分析应识别数据来源、测量方法和计算假设的不确定性。定量不确定性分析可使用蒙特卡洛模拟。不确定性应作为数据质量报告的一部分披露。",
                "metadata": {"topic": "不确定性分析", "category": "质量管理", "source": "ISO 14064"}
            }
        ]

        # 添加到知识库
        retriever = self._get_retriever()
        retriever.add_knowledge_batch(knowledge_items)

    def query(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """查询知识库"""
        retriever = self._get_retriever()
        return retriever.retrieve(question, top_k)

    def query_with_context(self, question: str, context: Optional[Dict[str, Any]] = None, top_k: int = 3) -> str:
        """带上下文的知识库查询"""
        retriever = self._get_retriever()

        # 根据上下文调整查询
        enhanced_query = question
        if context and context.get("current_section"):
            section_map = {
                1: "基本信息 企业",
                2: "产品 碳足迹 PCF",
                3: "燃料 燃烧 排放",
                4: "电力 热力 蒸汽",
                5: "制冷剂 逸散 GWP",
                6: "逸散 排放 CO2",
                7: "废水 废气 危废",
                8: "原材料 供应商",
                9: "耗材 新鲜水"
            }
            section_keyword = section_map.get(context["current_section"], "")
            if section_keyword:
                enhanced_query = f"{question} {section_keyword}"

        # 检索相关知识
        results = retriever.retrieve(enhanced_query, top_k)

        if not results:
            return "抱歉，我在知识库中没有找到相关信息，建议查阅国家标准或咨询专业人士。"

        # 生成回答
        context_knowledge = "\n\n".join([
            f"【{r.get('metadata', {}).get('topic', '未知')}】\n{r.get('content', '')}"
            for r in results
        ])

        return f"根据碳排放相关知识库，我为您提供以下信息：\n\n{context_knowledge}\n\n如果您需要更详细的解答，请告诉我具体是哪个方面。"

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        retriever = self._get_retriever()
        return retriever.get_stats()


# 全局知识库实例（延迟初始化）
_carbon_knowledge_base: Optional[CarbonKnowledgeBase] = None


def get_knowledge_base() -> CarbonKnowledgeBase:
    """获取知识库实例"""
    global _carbon_knowledge_base
    if _carbon_knowledge_base is None:
        _carbon_knowledge_base = CarbonKnowledgeBase()
    return _carbon_knowledge_base
