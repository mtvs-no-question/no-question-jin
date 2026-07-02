"""
역할:
    LangGraph 전체 워크플로우에서 공유할 상태(State)를 정의한다.

연결되는 파일:
    - manual_agent/workflow/graph.py
        StateGraph 생성 시 ManualAgentState를 사용한다.
    - manual_agent/workflow/nodes.py
        각 node 함수가 이 State를 입력받고 일부 값을 업데이트한다.
    - main.py
        최초 state를 만들어 graph.invoke(state)에 전달한다.

설계 의도:
    대화, 초안, 검수 결과, 승인 상태, 수정 요청 메시지, payload 결과를
    하나의 상태 객체로 관리한다.
"""

from typing import Any, Literal, TypedDict


class ManualAgentState(TypedDict, total=False):
    company_id: str
    conversation_id: str

    chat_messages: list[dict[str, str]]

    clarification_result: dict[str, Any]
    is_ready: bool
    assistant_message: str
    gathered_summary: str | None

    structured_task: dict[str, Any] | None
    existing_manual_context: list[dict[str, Any]]

    draft_result: dict[str, Any] | None
    quality_result: dict[str, Any] | None

    approval_status: Literal["pending", "approved", "revision_requested"]
    approval_feedback: str | None

    db_payload: dict[str, Any] | None
    vector_payload: list[dict[str, Any]]
    graph_payload: dict[str, Any] | None

    error: str | None