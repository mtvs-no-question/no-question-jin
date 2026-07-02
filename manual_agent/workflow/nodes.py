"""
역할:
    LangGraph에서 실행할 각 node 함수를 정의한다.

연결되는 파일:
    - manual_agent/workflow/graph.py
        여기서 정의한 node들을 StateGraph에 등록한다.
    - manual_agent/workflow/state.py
        ManualAgentState 타입을 사용한다.
    - manual_agent/llm/ai_structurer.py
        Clarification Agent와 Markdown Section Agent를 호출한다.
    - manual_agent/services/retrieval_service.py
        기존 매뉴얼 검색 기능을 호출한다.
    - manual_agent/services/quality_checker.py
        생성된 매뉴얼 초안을 검수한다.
    - manual_agent/services/approval.py
        로컬 승인 처리를 수행한다.
    - manual_agent/storage/payload_builder.py
        DB / VectorDB / GraphDB payload를 생성한다.
    - manual_agent/storage/sink.py
        생성된 payload를 출력한다.

수정 이유:
    Clarification Agent나 Markdown Section Agent가 정보 부족을 감지했을 때
    다음 node로 넘어가지 않고 사용자에게 추가 질문을 하도록 막는다.
"""

from typing import Any
from uuid import uuid4

from manual_agent.llm.ai_structurer import (
    run_clarification_agent,
    structure_request_with_ai,
)
from manual_agent.services.approval import ask_approval
from manual_agent.services.quality_checker import check_manual_section
from manual_agent.services.retrieval_service import search_existing_manual
from manual_agent.storage.payload_builder import (
    build_db_payload,
    build_graph_payload,
    build_vector_payload,
)
from manual_agent.storage.sink import PrintSink
from manual_agent.workflow.state import ManualAgentState
from manual_agent.processor import validate_structured_result


def _build_missing_fields_message(missing_fields: list[str]) -> str:
    questions = "\n".join(f"- {field}" for field in missing_fields)

    return (
        "매뉴얼 섹션을 만들기 전에 아래 정보가 더 필요합니다.\n\n"
        f"{questions}\n\n"
        "위 항목을 조금 더 구체적으로 알려주세요."
    )


def clarification_node(state: ManualAgentState) -> dict[str, Any]:
    result = run_clarification_agent(
        company_id=state["company_id"],
        chat_messages=state["chat_messages"],
    )

    missing_questions = result.get("missing_questions") or []
    gathered_summary = result.get("gathered_summary")

    is_ready = (
        bool(result.get("is_ready"))
        and len(missing_questions) == 0
        and bool(gathered_summary)
    )

    return {
        "clarification_result": result,
        "is_ready": is_ready,
        "assistant_message": result["assistant_message"],
        "gathered_summary": gathered_summary,
    }


def task_and_draft_node(state: ManualAgentState) -> dict[str, Any]:
    """
    역할:
        gathered_summary를 기반으로 Markdown Section Agent를 실행한다.

    연결되는 파일:
        - manual_agent/llm/ai_structurer.py
            structure_request_with_ai()를 호출한다.
        - manual_agent/processor.py
            validate_structured_result()를 재사용한다.
        - manual_agent/workflow/graph.py
            이 node 실행 후 기존 매뉴얼 검색 또는 품질 검수로 분기한다.

    주의:
        validate_structured_result()는 에러를 발생시키지 않고
        missing_fields list를 반환한다.
        따라서 반환값을 반드시 직접 확인해야 한다.
    """

    request = {
        "companyId": state["company_id"],
        "user_prompt": state["gathered_summary"],
    }

    structured_result = structure_request_with_ai(request)

    missing_fields = validate_structured_result(structured_result)

    if missing_fields:
        return {
            "is_ready": False,
            "assistant_message": _build_missing_fields_message(missing_fields),
            "structured_task": structured_result,
            "draft_result": None,
        }

    return {
        "structured_task": structured_result,
        "draft_result": structured_result,
    }


def existing_manual_search_node(state: ManualAgentState) -> dict[str, Any]:
    structured = state["structured_task"]

    context = search_existing_manual(
        company_id=state["company_id"],
        product_model=structured["product"]["model_name"],
        issue_topic=structured["issue_topic"],
    )

    return {
        "existing_manual_context": context,
    }


def quality_check_node(state: ManualAgentState) -> dict[str, Any]:
    result = check_manual_section(
        structured_result=state["draft_result"],
        existing_manual_context=state.get("existing_manual_context", []),
    )

    return {
        "quality_result": result,
    }


def approval_node(state: ManualAgentState) -> dict[str, Any]:
    result = ask_approval(state["draft_result"])

    status = result["approval_status"]
    feedback = result.get("approval_feedback")

    if status == "approved":
        assistant_message = "승인되었습니다. 저장용 payload를 생성합니다."
    else:
        assistant_message = (
            "초안을 수정하겠습니다. 추가하거나 바꾸고 싶은 내용을 입력해 주세요."
        )

    return {
        "approval_status": status,
        "approval_feedback": feedback,
        "assistant_message": assistant_message,
    }


def payload_build_node(state: ManualAgentState) -> dict[str, Any]:
    """
    역할:
        승인된 매뉴얼 초안을 DB / VectorDB / GraphDB payload로 변환한다.

    연결되는 파일:
        - manual_agent/storage/payload_builder.py
            build_db_payload()
            build_vector_payload()
            build_graph_payload()
        - manual_agent/workflow/graph.py
            approval_status가 approved일 때만 이 node로 진입한다.
        - manual_agent/workflow/nodes.py
            sink_node가 여기서 생성된 payload를 출력한다.

    중요:
        build_db_payload()의 실제 인자 순서는 processor.py 기준으로
        build_db_payload(job_id, request, structured) 이다.
    """

    job_id = str(uuid4())
    structured = state["draft_result"]

    request = {
        "companyId": state["company_id"],
        "user_prompt": state["gathered_summary"],
    }

    db_payload = build_db_payload(
        job_id,
        request,
        structured,
    )

    vector_payload = build_vector_payload(
        job_id,
        structured,
    )

    graph_payload = build_graph_payload(
        job_id,
        structured,
    )

    return {
        "db_payload": db_payload,
        "vector_payload": vector_payload,
        "graph_payload": graph_payload,
    }


def sink_node(state: ManualAgentState) -> dict[str, Any]:
    sink = PrintSink()

    sink.save_db_payload(state["db_payload"])
    sink.save_vector_payload(state["vector_payload"])
    sink.save_graph_payload(state["graph_payload"])

    return {}