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

from manual_agent.workflow.nodes import (
    approval_node,
    clarification_node,
    existing_manual_search_node,
    payload_build_node,
    quality_check_node,
    sink_node,
    task_and_draft_node,
)
from manual_agent.workflow.state import ManualAgentState


def route_after_clarification(
    state: ManualAgentState,
) -> Literal["task_and_draft", "end"]:
    if state.get("is_ready"):
        return "task_and_draft"

    return "end"


def route_after_task_and_draft(
    state: ManualAgentState,
) -> Literal["existing_manual_search", "quality_check", "end"]:
    structured = state.get("structured_task")

    if not structured:
        return "end"

    missing_fields = structured.get("missing_fields") or []
    if missing_fields:
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


def build_manual_agent_graph():
    graph = StateGraph(ManualAgentState)

    graph.add_node("clarification", clarification_node)
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

    return graph.compile()