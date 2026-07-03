"""
역할:
    manual_agent 프로젝트의 LangGraph 워크플로우를 정의한다.

연결되는 파일:
    - manual_agent/workflow/state.py
        ManualAgentState를 StateGraph의 상태 타입으로 사용한다.
    - manual_agent/workflow/nodes.py
        각 처리 단계를 node로 등록한다.
    - main.py
        build_manual_agent_graph()를 호출해 graph를 실행한다.

수정 이유:
    Markdown 구조화 결과에 missing_fields가 있으면
    기존 매뉴얼 검색, 품질 검수, 승인 단계로 넘어가지 않고 종료한다.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from manual_agent.workflow.nodes import (
    approval_node,
    clarification_node,
    existing_manual_search_node,
    payload_build_node,
    quality_check_node,
    sink_node,
    task_and_draft_node,
    manual_source_choice_node,
    manual_context_load_node,
)
from manual_agent.workflow.state import ManualAgentState


def route_after_clarification(
    state: ManualAgentState,
) -> Literal["manual_source_choice", "end"]:
    if state.get("is_ready"):
        return "manual_source_choice"

    return "end"


def route_after_task_and_draft(
    state: ManualAgentState,
) -> Literal["existing_manual_search", "quality_check", "end"]:
    """
    역할:
        task_and_draft_node 실행 후 다음 node를 결정한다.

    연결되는 파일:
        - manual_agent/workflow/nodes.py
            task_and_draft_node가 만든 structured_task, draft_result를 확인한다.
        - manual_agent/workflow/graph.py
            missing_fields 또는 draft_result 누락 시 다음 단계로 보내지 않는다.

    핵심:
        draft_result가 None이면 절대 quality_check로 보내면 안 된다.
    """

    structured = state.get("structured_task")
    draft = state.get("draft_result")

    if not structured:
        return "end"

    if draft is None:
        return "end"

    missing_fields = structured.get("missing_fields") or []
    if missing_fields:
        return "end"

    product = structured.get("product") or {}
    if not product.get("model_name"):
        return "end"

    needs_search = structured["manual_task"]["needs_existing_manual_search"]

    if needs_search:
        return "existing_manual_search"

    return "quality_check"


def route_after_quality_check(
    state: ManualAgentState,
) -> Literal["approval", "end"]:
    quality = state["quality_result"]

    if quality["passed"]:
        return "approval"

    return "end"


def route_after_approval(
    state: ManualAgentState,
) -> Literal["payload_build", "end"]:
    if state.get("approval_status") == "approved":
        return "payload_build"

    return "end"

def route_after_manual_source_choice(
    state: ManualAgentState,
) -> Literal["manual_context_load", "task_and_draft"]:
    if state.get("manual_source_mode") == "file":
        return "manual_context_load"

    return "task_and_draft"


def route_after_manual_context_load(
    state: ManualAgentState,
) -> Literal["task_and_draft", "end"]:
    if state.get("manual_context_available"):
        return "task_and_draft"

    return "end"

def build_manual_agent_graph(use_memory_checkpointer: bool = True):
    graph = StateGraph(ManualAgentState)

    graph.add_node("clarification", clarification_node)
    graph.add_node("manual_source_choice", manual_source_choice_node)
    graph.add_node("manual_context_load", manual_context_load_node)
    graph.add_node("task_and_draft", task_and_draft_node)
    graph.add_node("existing_manual_search", existing_manual_search_node)
    graph.add_node("quality_check", quality_check_node)
    graph.add_node("approval", approval_node)
    graph.add_node("payload_build", payload_build_node)
    graph.add_node("sink", sink_node)

    graph.add_edge(START, "clarification")

    graph.add_conditional_edges(
        "clarification",
        route_after_clarification,
        {
            "manual_source_choice": "manual_source_choice",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "manual_source_choice",
        route_after_manual_source_choice,
        {
            "manual_context_load": "manual_context_load",
            "task_and_draft": "task_and_draft",
        },
    )

    graph.add_conditional_edges(
        "manual_context_load",
        route_after_manual_context_load,
        {
            "task_and_draft": "task_and_draft",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "task_and_draft",
        route_after_task_and_draft,
        {
            "existing_manual_search": "existing_manual_search",
            "quality_check": "quality_check",
            "end": END,
        },
    )

    graph.add_edge("existing_manual_search", "quality_check")

    graph.add_conditional_edges(
        "quality_check",
        route_after_quality_check,
        {
            "approval": "approval",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "payload_build": "payload_build",
            "end": END,
        },
    )

    graph.add_edge("payload_build", "sink")
    graph.add_edge("sink", END)

    if use_memory_checkpointer:
        return graph.compile(checkpointer=InMemorySaver())

    return graph.compile()