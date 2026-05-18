"""
对话问答Agent - 碳管师收资系统
负责回答专业相关问题或闲聊
接入RAG知识库进行专业问题检索
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from tantan.backend.rag import get_rag_pipeline, get_rag_searcher, get_knowledge_base
from tantan.backend.utils import get_logger, log_exception

logger = get_logger(__name__)


class IntentType(str):
    """意图类型"""
    PROFESSIONAL_QUESTION = "professional_question"  # 专业问题
    GUIDANCE = "guidance"  # 填报指导
    CHITCHAT = "chitchat"  # 闲聊
    GENERAL_KNOWLEDGE = "general_knowledge"  # 通用知识/时间等
    UNKNOWN = "unknown"  # 未知


class QAAgent:
    """对话问答Agent"""

    # 系统提示词
    SYSTEM_PROMPT = """你是碳管师收资系统的AI助手，专门帮助用户完成碳排放数据填报工作。

当前时间：{current_time}

你的职责：
1. 回答碳排放相关的专业问题（范围1/2/3排放、碳足迹计算、排放因子等）
2. 提供PCF（产品碳足迹）核算的填报指导
3. 解答用户关于表单填写的问题
4. 回答一般性问题（如当前时间等）

回答要求：
- 简洁、专业、易懂
- 如果不确定，可以说明"我不太确定，但建议您..."
- 对于专业问题，尽量引用相关标准或指南
- 不要回答超出碳排放领域的问题（如政治、色情等）

记住：当前时间是 {current_time}，如果用户问时间，请如实回答。"""

    def __init__(self):
        self.conversation_history: List[Dict[str, Any]] = []
        self.session_id: Optional[str] = None
        self._rag_pipeline = None
        self._rag_searcher = None

    @property
    def rag_pipeline(self):
        """延迟加载RAG管道"""
        if self._rag_pipeline is None:
            self._rag_pipeline = get_rag_pipeline()
        return self._rag_pipeline

    @property
    def rag_searcher(self):
        """延迟加载RAG搜索器"""
        if self._rag_searcher is None:
            self._rag_searcher = get_rag_searcher()
        return self._rag_searcher

    def set_session(self, session_id: str) -> None:
        """设置会话ID"""
        self.session_id = session_id

    def _get_current_time_str(self) -> str:
        """获取当前时间字符串"""
        now = datetime.now()
        return now.strftime("%Y年%m月%d日 %H:%M:%S %A")

    def analyze_intent(self, message: str) -> IntentType:
        """分析用户消息的意图"""
        message_lower = message.lower()

        # 时间相关的问题
        time_keywords = ["时间", "几点", "现在几点", "今天几号", "日期", "星期几", "什么日子"]
        if any(kw in message for kw in time_keywords):
            return IntentType.GENERAL_KNOWLEDGE

        # 碳排放专业词汇
        carbon_topics = [
            "碳排放", "碳核算", "碳足迹", "PCF", "温室气体",
            "范围1", "范围2", "范围3", "二氧化碳", "甲烷",
            "减排", "碳中和", "碳交易", "碳配额", "CCER",
            "碳因子", "IPCC", "活动水平", "排放因子",
            "GWP", "全球变暖", "化石燃料", "电力排放"
        ]
        for topic in carbon_topics:
            if topic in message_lower:
                return IntentType.PROFESSIONAL_QUESTION

        # 填报指导关键词
        guidance_keywords = ["怎么填", "如何填写", "不知道", "帮助", "指导", "提示", "例子", "怎么填表"]
        for keyword in guidance_keywords:
            if keyword in message_lower:
                return IntentType.GUIDANCE

        # 问候
        greetings = ["你好", "您好", "hi", "hello", "嗨", "hey", "在吗", "在不在"]
        for greeting in greetings:
            if greeting in message_lower:
                return IntentType.CHITCHAT

        # 告别
        farewells = ["再见", "拜拜", "bye", "下次见", "结束"]
        for farewell in farewells:
            if farewell in message_lower:
                return IntentType.CHITCHAT

        # 简单问题（数字计算、天气、时间等）
        simple_keywords = ["多少", "计算", "天气", "新闻", "百科"]
        if any(kw in message for kw in simple_keywords) and len(message) < 30:
            return IntentType.GENERAL_KNOWLEDGE

        return IntentType.UNKNOWN

    def generate_response(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成回复"""
        intent = self.analyze_intent(message)
        current_time = self._get_current_time_str()

        response = {
            "msg_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        }

        if intent == IntentType.GENERAL_KNOWLEDGE:
            response["content"] = self._answer_general_question(message, current_time)
            response["type"] = "general_answer"
        elif intent == IntentType.PROFESSIONAL_QUESTION:
            response["content"] = self._answer_professional_question(message, context)
            response["type"] = "professional_answer"
        elif intent == IntentType.GUIDANCE:
            response["content"] = self._provide_guidance(message, context)
            response["type"] = "guidance"
        elif intent == IntentType.CHITCHAT:
            response["content"] = self._handle_chitchat(message)
            response["type"] = "chitchat"
        else:
            response["content"] = self._handle_unknown(message, current_time)
            response["type"] = "unknown"

        self.conversation_history.append({
            "user": message,
            "assistant": response["content"],
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        })

        return response

    def _answer_general_question(self, question: str, current_time: str) -> str:
        """回答通用问题（时间等）"""
        question_lower = question.lower()

        # 时间问题
        if any(kw in question for kw in ["时间", "几点", "现在", "几号", "日期"]):
            return f"当前时间是：{current_time}"

        # 如果RAG可用，尝试用LLM回答
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT.format(current_time=current_time)},
                {"role": "user", "content": question}
            ]
            result = self._call_llm(messages)
            if result:
                return result
        except Exception as e:
            logger.error(f"LLM调用失败: {str(e)}", exc_info=True)

        # 降级到规则回答
        return f"当前时间是：{current_time}"

    def _call_llm(self, messages: List[Dict[str, str]], stream: bool = False) -> Optional[str]:
        """调用LLM生成回答"""
        try:
            llm_client = get_llm_client()
            result = llm_client.chat(messages, stream=stream)
            if isinstance(result, dict) and result.get("content"):
                return result["content"]
            return None
        except Exception as e:
            logger.error(f"LLM响应失败: {str(e)}", exc_info=True)
            return None

    def _answer_professional_question(self, question: str, context: Optional[Dict[str, Any]]) -> str:
        """回答专业问题 - 通过RAG管道（检索+LLM生成）"""
        try:
            # 使用RAG管道生成答案
            result = self.rag_pipeline.answer(question, context, include_sources=False)
            return result.get("answer", "")
        except Exception as e:
            logger.error(f"RAG管道执行失败: {str(e)}", exc_info=True)
            # 降级到直接LLM调用
            current_time = self._get_current_time_str()
            try:
                messages = [
                    {"role": "system", "content": self.SYSTEM_PROMPT.format(current_time=current_time)},
                    {"role": "user", "content": question}
                ]
                result = self._call_llm(messages)
                if result:
                    return result
            except Exception as e2:
                logger.error(f"LLM降级失败: {str(e2)}", exc_info=True)

            # 最终降级到规则回答
            return self._rule_based_answer(question)

    def _rule_based_answer(self, question: str) -> str:
        """基于规则的回答（最终备用）"""
        question_lower = question.lower()

        if "范围1" in question_lower or "范围一" in question_lower:
            return (
                "范围1排放是指企业拥有或控制的排放源产生的直接温室气体排放。\n"
                "主要包括：\n"
                "1. 固定源燃烧（如锅炉、发电机）\n"
                "2. 移动源燃烧（如公司车辆）\n"
                "3. 逸散排放（如制冷剂泄漏）\n"
                "4. 过程排放（如工业过程）"
            )

        if "范围2" in question_lower or "范围二" in question_lower:
            return (
                "范围2排放是指企业外购电力、热力、蒸汽产生的间接温室气体排放。\n"
                "这些排放发生在生产这些能源的地点，但由企业消费这些能源而产生。"
            )

        if "碳因子" in question_lower or "排放因子" in question_lower:
            return (
                "碳排放因子是将活动水平数据转换为温室气体排放量的系数。\n"
                "常用单位：kgCO2e/unit（如 kgCO2e/kWh, kgCO2e/t）\n"
                "数据来源：IPCC、GB/T 32151、生态环境部公告等"
            )

        if "绿证" in question_lower or "绿色电力" in question_lower:
            return (
                "绿色电力证书（绿证）是用于证明电力来自可再生能源的凭证。\n"
                "国内主要有中国绿证GEC、国际绿证IREC和TIGR等。\n"
                "购买绿证可以抵扣外购电力的碳排放。"
            )

        if "制冷剂" in question_lower:
            return (
                "制冷剂排放是逸散排放的重要组成部分。\n"
                "计算方法：制冷剂填充量(kg) × 泄漏率 × GWP值。\n"
                "常用制冷剂：R410A（GWP=2088）、R134a（GWP=1430）、R32（GWP=675）。"
            )

        if "废水" in question_lower and "处理" in question_lower:
            return (
                "废水处理过程中会产生甲烷逸散，属于范围1排放。\n"
                "计算因素包括：废水排放量、BOD浓度、甲烷转化因子(MCF)、BOD去除率。\n"
                "厌氧处理工艺会产生甲烷，需要特别注意。"
            )

        return (
            "这是一个关于碳排放的专业问题。\n"
            "如果您需要更详细的解答，建议查阅相关国家标准或咨询碳管师。\n"
            "您也可以通过上传文件的方式，让系统帮您自动提取和计算。"
        )

    def _provide_guidance(self, question: str, context: Optional[Dict[str, Any]]) -> str:
        """提供填报指导"""
        current_section = context.get("current_section", 1) if context else 1

        section_guides = {
            1: "基本信息部分需要填写企业名称、所属行业、联系人等信息。请确保企业名称与营业执照一致。",
            2: "产品部分需要填写PCF核算目标产品名称、是否唯一产品、计量单位等信息。",
            3: "燃料使用部分需要填写各种燃烧设备的燃料类型和核算周期内的使用量。",
            4: "电力、热力使用部分需要填写用电单元的统计情况和蒸汽参数。",
            5: "制冷剂使用部分需要填写空调和冷冻机的制冷剂标号及填充量。",
            6: "其他散逸类排放部分需要填写CO2灭火器的填充总量和员工总工时。",
            7: "三废处理部分需要填写废水废气处理方式和危废处理量。",
            8: "原材料使用部分需要填写PCF核算目标产品的原材料清单和供应商信息。",
            9: "生产耗材部分需要填写新鲜水和氮气的使用量及统计口径。"
        }

        if any(kw in question for kw in ["当前", "现在", "这部分"]):
            return f"当前您正在填写第{current_section}部分：{section_guides.get(current_section, '未知部分')}"

        return (
            f"目前您正在进行第{current_section}部分的填报。\n"
            f"{section_guides.get(current_section, '')}\n\n"
            "您可以：\n"
            "1. 直接在表单中填写数据\n"
            "2. 上传Excel文件，系统会自动提取数据\n"
            "3. 随时暂停并切换到其他部分"
        )

    def _handle_chitchat(self, message: str) -> str:
        """处理闲聊"""
        message_lower = message.lower()
        current_time = self._get_current_time_str()

        for farewell in ["再见", "拜拜", "bye", "下次见"]:
            if farewell in message_lower:
                return "好的，再见！如有问题随时联系我。"

        for greeting in ["你好", "您好", "hi", "hello", "嗨", "hey", "在吗", "在不在"]:
            if greeting in message_lower:
                return f"您好！我是碳管师助手，请问有什么可以帮助您的？\n当前时间：{current_time}"

        return f"您好！请问还有什么需要帮助的？"

    def _handle_unknown(self, message: str, current_time: str) -> str:
        """处理未知意图"""
        # 尝试用LLM回答
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT.format(current_time=current_time)},
                {"role": "user", "content": message}
            ]
            result = self._call_llm(messages)
            if result:
                return result
        except Exception as e:
            logger.error(f"未知意图LLM处理失败: {str(e)}", exc_info=True)

        return (
            "抱歉，我不太理解您的问题。\n"
            "您可以：\n"
            "1. 询问碳排放相关的专业问题\n"
            "2. 请求填报指导\n"
            "3. 上传文件让系统帮您自动提取数据"
        )

    def search_knowledge_base(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """搜索知识库（RAG检索）"""
        search_results = self.rag_searcher.search(query, top_k=top_k)
        return [
            {
                "content": result.content,
                "topic": result.metadata.get("topic", "未知"),
                "source": result.metadata.get("source", "未知"),
                "score": result.score
            }
            for result in search_results
        ]

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self.conversation_history


class KnowledgeBase_retriever:
    """知识库检索器（用于RAG）- 保留以兼容旧代码"""

    def __init__(self):
        self._rag_searcher = None

    @property
    def rag_searcher(self):
        """延迟加载RAG搜索器"""
        if self._rag_searcher is None:
            self._rag_searcher = get_rag_searcher()
        return self._rag_searcher

    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载知识库"""
        kb = get_knowledge_base()
        stats = kb.get_stats()
        return [
            {
                "topic": "碳排放核算",
                "content": f"知识库共有{stats['total_chunks']}条知识条目",
                "source": "RAG知识库"
            }
        ]

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索相关知识"""
        results = self.rag_searcher.search(query, top_k=top_k)
        return [
            {
                "topic": r.metadata.get("topic", "未知"),
                "content": r.content,
                "source": r.metadata.get("source", "未知")
            }
            for r in results
        ]