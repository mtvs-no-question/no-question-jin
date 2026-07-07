"""
파일명:
    manual_agent/runtime/runner.py

역할:
    LangGraph 실행, interrupt 추출, resume 처리를 공통 함수로 제공한다.

연결되는 파일:
    - web_app.py
        브라우저 채팅 UI에서 들어온 요청을 이 파일의 함수로 실행한다.
    - main.py
        나중에 원하면 CLI도 이 파일을 사용하도록 단순화할 수 있다.
    - manual_agent/workflow/graph.py
        build_manual_agent_graph()를 호출한다.

설계 의도:
    main.py, FastAPI, LangGraph Studio 같은 실행 환경이 달라도
    graph 실행 방식은 이 파일을 중심으로 공유한다.

주의:
    state에는 JSON 직렬화 가능한 데이터만 넣는다.
    OpenAI client, DB client, file handle 같은 객체는 state에 넣지 않는다.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from manual_agent.workflow.graph import build_manual_agent_graph


DEFAULT_COMPANY_ID = "019f1b62-dd8f-77f9-8500-22881b24065f"


def create_graph_for_local_server():
    """
    역할:
        로컬 웹 서버에서 사용할 graph를 생성한다.

    설명:
        CLI / 로컬 FastAPI에서는 interrupt resume을 위해 memory checkpointer가 필요하다.
        단, 사용자의 graph.py가 아직 use_memory_checkpointer 인자를 지원하지 않는 경우도
        호환되도록 TypeError fallback을 둔다.
    """

    try:
        return build_manual_agent_graph(use_memory_checkpointer=True)
    except TypeError:
        return build_manual_agent_graph()


def build_config(
    thread_id: str,
    company_id: str = DEFAULT_COMPANY_ID,
    entrypoint: str = "web_app.py",
) -> dict[str, Any]:
    """
    역할:
        LangGraph invoke에 전달할 config를 만든다.

    중요:
        checkpointer를 사용하는 graph는 configurable.thread_id가 반드시 필요하다.
    """

    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "tags": ["manual-agent", "frontend", "local-web"],
        "metadata": {
            "company_id": company_id,
            "thread_id": thread_id,
            "entrypoint": entrypoint,
        },
    }


def build_state(
    *,
    company_id: str,
    conversation_id: str,
    chat_messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    역할:
        LangGraph에 넣을 기본 state를 만든다.

    연결되는 파일:
        - manual_agent/workflow/state.py
            이 state 구조와 호환되어야 한다.
    """

    return {
        "company_id": company_id,
        "conversation_id": conversation_id,
        "chat_messages": chat_messages,
        "existing_manual_context": [],
        "approval_status": "pending",
        "approval_feedback": None,
        "manual_source_mode": None,
        "manual_file_path": None,
        "manual_context": None,
        "manual_context_available": False,
        "vector_payload": [],
    }


def get_interrupt_payload(result: dict[str, Any]) -> Any | None:
    """
    역할:
        graph.invoke 결과에서 interrupt payload만 추출한다.
    """

    interrupts = result.get("__interrupt__")

    if not interrupts:
        return None

    first_interrupt = interrupts[0]

    return getattr(first_interrupt, "value", first_interrupt)


def normalize_result(thread_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """
    역할:
        LangGraph 결과를 프론트엔드가 다루기 쉬운 JSON 형태로 변환한다.
    """

    interrupt_payload = get_interrupt_payload(result)

    if interrupt_payload:
        return {
            "status": "interrupted",
            "thread_id": thread_id,
            "interrupt": interrupt_payload,
            "message": _message_from_interrupt(interrupt_payload),
        }

    response: dict[str, Any] = {
        "status": "completed",
        "thread_id": thread_id,
        "message": result.get("assistant_message"),
        "approval_status": result.get("approval_status"),
        "quality_result": result.get("quality_result"),
        "is_ready": result.get("is_ready"),
    }

    draft = result.get("draft_result") or {}
    manual_section = draft.get("manual_section") or {}
    markdown = manual_section.get("markdown")

    if markdown:
        response["draft_markdown"] = markdown

    if result.get("approval_status") == "approved" and markdown:
        response["final_markdown"] = markdown
        response["message"] = response["message"] or "승인되었습니다. 최종 Markdown이 생성되었습니다."

    quality = result.get("quality_result")
    if quality and not quality.get("passed", False):
        response["status"] = "quality_failed"
        response["message"] = "품질 검수에 실패했습니다. 입력 정보를 보완해 주세요."

    if response.get("is_ready") is False:
        response["status"] = "waiting_for_user"

    return response


def invoke_graph(
    *,
    graph: Any,
    state: dict[str, Any],
    thread_id: str,
    company_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    역할:
        새 사용자 메시지가 들어왔을 때 graph를 실행한다.

    반환:
        - 프론트엔드 응답용 dict
        - 원본 LangGraph result
    """

    config = build_config(thread_id=thread_id, company_id=company_id)
    result = graph.invoke(state, config=config)

    return normalize_result(thread_id, result), result


def resume_graph(
    *,
    graph: Any,
    thread_id: str,
    company_id: str,
    resume_value: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    역할:
        interrupt 이후 사용자의 응답을 Command(resume=...)로 graph에 다시 넣는다.
    """

    config = build_config(thread_id=thread_id, company_id=company_id)
    result = graph.invoke(Command(resume=resume_value), config=config)

    return normalize_result(thread_id, result), result


def _message_from_interrupt(interrupt_payload: Any) -> str:
    if isinstance(interrupt_payload, dict):
        return str(interrupt_payload.get("message") or "사용자 확인이 필요합니다.")

    return str(interrupt_payload)
