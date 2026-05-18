"""
核心流程控制Agent - 碳管师收资系统
使用 LangGraph 实现多 Agent 状态机编排
"""

import uuid
import operator
from datetime import datetime
from typing import Optional, Dict, Any, List, Annotated, Literal, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from tantan.backend.config import get_config
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


# ============ State 定义 ============

class SectionStatus(str):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRM = "awaiting_confirm"
    COMPLETED = "completed"
    MODIFIED = "modified"


class AgentStatus(str):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FormAgentState(TypedDict):
    """LangGraph 状态定义"""
    session_id: str
    messages: Annotated[list, "append"]
    current_section: int
    form_data: dict
    section_status: dict
    agent_result: Optional[dict]
    error: Optional[str]
    next_action: Optional[str]


# ============ Node 函数 ============

def intake_node(state: FormAgentState) -> FormAgentState:
    """接收用户输入，解析消息类型"""
    if not state.get("messages"):
        return state

    last_message = state["messages"][-1]
    msg_type = last_message.get("type", "chat")

    routing = {
        "file_upload": "file_extract",
        "form_fill": "form_fill",
        "chat": "qa",
        "modify": "modify"
    }
    next_action = routing.get(msg_type, "qa")

    return {
        **state,
        "next_action": next_action,
        "agent_result": None,
        "error": None
    }


def route_node(state: FormAgentState) -> Literal["qa", "file_extract", "form_fill", "modify", "confirm"]:
    """路由到合适的 Agent"""
    action = state.get("next_action", "qa")
    return action


def qa_node(state: FormAgentState) -> FormAgentState:
    """问答 Agent"""
    from tantan.backend.agents.qa_agent import QAAgent

    try:
        last_message = state["messages"][-1]
        question = last_message.get("content", "")

        agent = QAAgent()
        agent.set_session(state["session_id"])

        result = agent.generate_response(question, context={"current_section": state["current_section"]})

        return {
            **state,
            "agent_result": result,
            "next_action": "confirm"
        }
    except Exception as e:
        logger.error(f"QA节点执行失败: session_id={state.get('session_id')}, error: {str(e)}", exc_info=True)
        return {
            **state,
            "error": str(e),
            "agent_result": {"error": str(e)},
            "next_action": "confirm"
        }


def file_extract_node(state: FormAgentState) -> FormAgentState:
    """文件提取 Agent"""
    from tantan.backend.agents.file_extractor import FileExtractAgent

    try:
        last_message = state["messages"][-1]
        file_content = last_message.get("file_content")
        section = last_message.get("section", state["current_section"])

        agent = FileExtractAgent(section=section)
        result = agent.process(file_content)

        return {
            **state,
            "agent_result": result,
            "next_action": "form_fill"
        }
    except Exception as e:
        logger.error(f"文件提取节点执行失败: session_id={state.get('session_id')}, error: {str(e)}", exc_info=True)
        return {
            **state,
            "error": str(e),
            "agent_result": {"error": str(e)},
            "next_action": "confirm"
        }


def form_fill_node(state: FormAgentState) -> FormAgentState:
    """表单填报 Agent"""
    from tantan.backend.agents.form_filler import FormFillAgent

    try:
        extracted_data = state.get("agent_result", {}).get("data", {})
        section = state["current_section"]

        agent = FormFillAgent(section=section)
        result = agent.fill_form(extracted_data)

        # 更新 form_data
        new_form_data = dict(state["form_data"])
        new_form_data[section] = result.get("filled_data", {})

        return {
            **state,
            "form_data": new_form_data,
            "agent_result": result,
            "next_action": "confirm"
        }
    except Exception as e:
        logger.error(f"表单填报节点执行失败: session_id={state.get('session_id')}, error: {str(e)}", exc_info=True)
        return {
            **state,
            "error": str(e),
            "agent_result": {"error": str(e)},
            "next_action": "confirm"
        }


def modify_node(state: FormAgentState) -> FormAgentState:
    """修改 Agent"""
    from tantan.backend.agents.modify_agent import ModifyAgent

    try:
        last_message = state["messages"][-1]
        modification = last_message.get("modification", {})

        agent = ModifyAgent()
        result = agent.process_modify_request(
            section=modification.get("section"),
            field=modification.get("field"),
            old_value=modification.get("old_value"),
            new_value=modification.get("new_value"),
            reason=modification.get("reason", ""),
            current_data=state["form_data"].get(modification.get("section"))
        )

        return {
            **state,
            "agent_result": result,
            "next_action": "confirm"
        }
    except Exception as e:
        logger.error(f"修改节点执行失败: session_id={state.get('session_id')}, error: {str(e)}", exc_info=True)
        return {
            **state,
            "error": str(e),
            "agent_result": {"error": str(e)},
            "next_action": "confirm"
        }


def confirm_node(state: FormAgentState) -> FormAgentState:
    """确认节点"""
    section = state["current_section"]

    # 更新 section status
    new_status = dict(state["section_status"])
    if section in new_status:
        new_status[section] = SectionStatus.COMPLETED

    return {
        **state,
        "section_status": new_status,
        "agent_result": None
    }


def should_continue(state: FormAgentState) -> Literal["intake", END]:
    """判断是否继续还是结束"""
    if state.get("error"):
        return END
    next_action = state.get("next_action")
    if next_action in ["qa", "file_extract", "form_fill", "modify"]:
        return "intake"
    return END


# ============ LangGraph 工作流 ============

def create_form_agent_graph():
    """创建表单Agent工作流图"""

    workflow = StateGraph(FormAgentState)

    # 添加节点
    workflow.add_node("intake", intake_node)
    workflow.add_node("route", route_node)
    workflow.add_node("qa", qa_node)
    workflow.add_node("file_extract", file_extract_node)
    workflow.add_node("form_fill", form_fill_node)
    workflow.add_node("modify", modify_node)
    workflow.add_node("confirm", confirm_node)

    # 设置入口点
    workflow.set_entry_point("intake")

    # intake -> route
    workflow.add_edge("intake", "route")

    # route -> 各 Agent（条件边）
    workflow.add_conditional_edges(
        "route",
        lambda s: s.get("next_action", "qa"),
        {
            "qa": "qa",
            "file_extract": "file_extract",
            "form_fill": "form_fill",
            "modify": "modify",
            "confirm": "confirm"
        }
    )

    # Agent -> confirm
    workflow.add_edge("qa", "confirm")
    workflow.add_edge("file_extract", "confirm")
    workflow.add_edge("form_fill", "confirm")
    workflow.add_edge("modify", "confirm")

    # confirm -> intake（循环）或 END
    workflow.add_conditional_edges(
        "confirm",
        should_continue,
        {
            "intake": "intake",
            END: END
        }
    )

    # 编译
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# ============ OrchestratorAgent ============

class OrchestratorAgent:
    """核心流程控制Agent - 适配 LangGraph"""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.graph = create_form_agent_graph()
        self._config = {"configurable": {"thread_id": self.session_id}}

        # 初始化状态
        self._initial_state = {
            "session_id": self.session_id,
            "messages": [],
            "current_section": 1,
            "form_data": {i: {} for i in range(1, 10)},
            "section_status": {
                i: SectionStatus.NOT_STARTED for i in range(1, 10)
            },
            "agent_result": None,
            "error": None,
            "next_action": None
        }

    def create_session(self) -> Dict[str, Any]:
        """创建新会话"""
        return {
            "session_id": self.session_id,
            "progress": self.get_progress(),
            "current_section": self._initial_state["current_section"],
            "created_at": datetime.now().isoformat()
        }

    def get_progress(self) -> Dict[str, Any]:
        """获取进度状态（从图状态恢复）"""
        try:
            state = self.graph.get_state(self._config)
            return {
                "sections": state.values.get("section_status", self._initial_state["section_status"]),
                "current_section": state.values.get("current_section", 1)
            }
        except Exception as e:
            logger.warning(f"获取进度状态失败，使用默认状态: {str(e)}")
            return {
                "sections": self._initial_state["section_status"],
                "current_section": self._initial_state["current_section"]
            }

    def update_section_status(self, section: int, status: SectionStatus) -> None:
        """更新部分状态"""
        self._initial_state["section_status"][section] = status

    def set_current_section(self, section: int) -> Dict[str, Any]:
        """设置当前部分"""
        if 1 <= section <= 9:
            self._initial_state["current_section"] = section
            self._initial_state["section_status"][section] = SectionStatus.IN_PROGRESS
            return {
                "success": True,
                "current_section": section,
                "section_name": self._get_section_name(section)
            }
        return {"success": False, "error": "无效的部分编号"}

    def route_message(self, message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """路由消息到合适的Agent"""
        message = {
            "type": message_type,
            **payload
        }

        state = {
            **self._initial_state,
            "messages": [message],
            "next_action": message_type
        }

        result = self.graph.invoke(state, self._config)

        self._initial_state = result

        return {
            "msg_id": str(uuid.uuid4()),
            "type": result.get("next_action", "unknown"),
            "section": result.get("current_section", 1),
            "session_id": self.session_id,
            "payload": result.get("agent_result", {}),
            "timestamp": datetime.now().isoformat(),
            "status": "completed" if not result.get("error") else "failed"
        }

    def get_next_section(self) -> int:
        """获取下一个待填报的部分"""
        status = self._initial_state["section_status"]
        for section_num in range(1, 10):
            if status.get(section_num) in [SectionStatus.NOT_STARTED, SectionStatus.IN_PROGRESS]:
                return section_num
        return 9

    def confirm_section(self, section: int) -> Dict[str, Any]:
        """确认某部分完成"""
        if section in self._initial_state["section_status"]:
            self._initial_state["section_status"][section] = SectionStatus.COMPLETED

            next_section = self.get_next_section()
            if next_section <= 9:
                self._initial_state["current_section"] = next_section
                self._initial_state["section_status"][next_section] = SectionStatus.IN_PROGRESS

            return {
                "success": True,
                "completed_section": section,
                "next_section": next_section,
                "progress": self.get_progress()
            }
        return {"success": False, "error": "无效的部分编号"}

    def save_form_data(self, section: int, data: Dict[str, Any]) -> None:
        """保存表单数据"""
        if 1 <= section <= 9:
            self._initial_state["form_data"][section].update(data)

    def get_form_data(self, section: Optional[int] = None) -> Dict[str, Any]:
        """获取表单数据"""
        if section:
            return self._initial_state["form_data"].get(section, {})
        return self._initial_state["form_data"]

    def _get_section_name(self, section: int) -> str:
        names = {
            1: "基本信息", 2: "产品", 3: "燃料使用",
            4: "电力、热力使用", 5: "制冷剂使用",
            6: "其他散逸类排放", 7: "三废处理",
            8: "原材料使用", 9: "生产耗材"
        }
        return names.get(section, "未知")


class FormProgress:
    """表单进度状态机 - 保留兼容"""

    def __init__(self):
        self.sections = {
            1: {"name": "基本信息", "status": SectionStatus.NOT_STARTED},
            2: {"name": "产品", "status": SectionStatus.NOT_STARTED},
            3: {"name": "燃料使用", "status": SectionStatus.NOT_STARTED},
            4: {"name": "电力、热力使用", "status": SectionStatus.NOT_STARTED},
            5: {"name": "制冷剂使用", "status": SectionStatus.NOT_STARTED},
            6: {"name": "其他散逸类排放", "status": SectionStatus.NOT_STARTED},
            7: {"name": "三废处理", "status": SectionStatus.NOT_STARTED},
            8: {"name": "原材料使用", "status": SectionStatus.NOT_STARTED},
            9: {"name": "生产耗材", "status": SectionStatus.NOT_STARTED},
        }
        self.current_section = 1

    def get_next_action(self) -> Dict[str, Any]:
        if self._has_user_input():
            return self._route_to_agent()
        elif self._section_completed():
            return self._enable_next_section()
        else:
            return {"action": "wait", "message": "等待用户输入"}

    def _has_user_input(self) -> bool:
        return False

    def _route_to_agent(self) -> Dict[str, Any]:
        return {"action": "route", "agent": "unknown"}

    def _section_completed(self) -> bool:
        return False

    def _enable_next_section(self) -> Dict[str, Any]:
        if self.current_section < 9:
            self.current_section += 1
            self.sections[self.current_section]["status"] = SectionStatus.IN_PROGRESS
            return {
                "action": "enable_section",
                "section": self.current_section,
                "message": f"已开启第{self.current_section}部分：{self.sections[self.current_section]['name']}"
            }
        return {"action": "all_completed", "message": "所有部分已完成"}