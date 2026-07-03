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

from langgraph.types import interrupt

from manual_agent.llm.ai_structurer import (
    run_clarification_agent,
    structure_request_with_ai,
)
from manual_agent.services.quality_checker import check_manual_section
from manual_agent.services.retrieval_service import search_existing_manual
from manual_agent.services.manual_source import load_manual_context
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

def manual_source_choice_node(state: ManualAgentState) -> dict[str, Any]:
    """
    역할:
        Markdown 초안을 만들기 전에 제품 매뉴얼 원문을 사용할지 사용자에게 확인한다.

    연결되는 파일:
        - manual_agent/workflow/graph.py
            clarification 이후 이 node로 진입한다.
        - manual_agent/services/manual_source.py
            파일을 사용할 경우 manual_context_load_node에서 실제 파일을 읽는다.

    interrupt 사용 이유:
        input()을 직접 쓰지 않고 LangGraph 실행을 멈춘 뒤,
        Studio / API / CLI에서 resume 입력으로 다시 진행하기 위해 사용한다.
    """

    answer = interrupt(
        {
            "type": "manual_source_choice",
            "message": (
                "제품 매뉴얼 원문을 참고해서 작성할까요?\n\n"
                "- PDF / MD / TXT 파일 경로를 입력하면 해당 파일을 참고합니다.\n"
                "- 매뉴얼 없이 기존 방식으로 진행하려면 skip을 입력하세요."
            ),
            "examples": [
                r"C:\Users\Admin\Desktop\EUSI-2941_manual.pdf",
                "skip",
            ],
        }
    )

    user_input = str(answer).strip().strip('"')

    if user_input.lower() in ["skip", "s", "no", "아니", "없음"]:
        return {
            "manual_source_mode": "skip",
            "manual_file_path": None,
            "manual_context": None,
            "manual_context_available": False,
        }

    return {
        "manual_source_mode": "file",
        "manual_file_path": user_input,
    }

def manual_context_load_node(state: ManualAgentState) -> dict[str, Any]:
    """
    역할:
        사용자가 입력한 제품 매뉴얼 파일 경로를 읽어서 manual_context를 만든다.

    연결되는 파일:
        - manual_agent/services/manual_source.py
            load_manual_context()를 호출한다.
        - manual_agent/workflow/graph.py
            manual_context_available 값에 따라 task_and_draft로 갈지 종료할지 결정한다.
        - task_and_draft_node
            manual_context를 LLM 요청에 포함한다.

    실패 처리:
        파일 경로가 잘못되었거나 읽기 실패하면 is_ready=False로 두고
        사용자에게 다시 입력을 요청한다.
    """

    try:
        manual_context = load_manual_context(state["manual_file_path"])

        return {
            "manual_context": manual_context,
            "manual_context_available": True,
        }

    except Exception as error:
        return {
            "is_ready": False,
            "manual_context": None,
            "manual_context_available": False,
            "assistant_message": (
                "매뉴얼 파일을 읽지 못했습니다.\n"
                f"원인: {error}\n\n"
                "파일 경로를 다시 확인하거나, skip을 입력해 매뉴얼 없이 진행할 수 있습니다."
            ),
            "error": str(error),
        }

def task_and_draft_node(state: ManualAgentState) -> dict[str, Any]:
    """
    역할:
        gathered_summary를 기반으로 구조화 결과와 Markdown 초안을 생성한다.

    연결되는 파일:
        - manual_agent/llm/ai_structurer.py
            structure_request_with_ai()를 호출한다.
        - manual_agent/processor.py
            validate_structured_result()를 호출해 필수값 누락 여부를 확인한다.
        - manual_agent/workflow/graph.py
            draft_result가 None이면 다음 단계로 진행하지 않는다.

    핵심:
        product.model_name 같은 필수값이 없으면 draft_result를 None으로 두고,
        assistant_message를 통해 사용자에게 추가 정보를 요청한다.
    """

    request = {
        "companyId": state["company_id"],
        "user_prompt": state["gathered_summary"],
        "manual_source_mode": state.get("manual_source_mode"),
        "manual_context_available": state.get("manual_context_available", False),
        "manual_context": state.get("manual_context"),
    }

    structured_result = structure_request_with_ai(request)

    missing_fields = validate_structured_result(structured_result)

    if missing_fields:
        structured_result["missing_fields"] = missing_fields

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
    """
    역할:
        생성된 매뉴얼 초안을 사용자에게 보여주고 승인 또는 수정 요청을 받는다.

    연결되는 파일:
        - manual_agent/workflow/graph.py
            approval_status가 approved면 payload_build로 이동한다.
        - main.py
            interrupt 발생 시 Command(resume=...)로 사용자 응답을 다시 넣는다.

    interrupt 사용 이유:
        기존 input() 방식은 LangSmith Studio / API 실행에서 멈춤 문제가 생긴다.
        interrupt는 LangGraph 표준 방식으로 실행을 중단하고 재개할 수 있다.
    """

    markdown = state["draft_result"]["manual_section"]["markdown"]

    answer = interrupt(
        {
            "type": "approval",
            "message": "아래 매뉴얼 초안을 승인하시겠습니까?",
            "markdown": markdown,
            "options": [
                "승인",
                "approve",
                "수정할 내용을 직접 입력",
            ],
        }
    )

    user_input = str(answer).strip()

    if user_input.lower() in ["approve", "approved", "y", "yes", "승인"]:
        return {
            "approval_status": "approved",
            "approval_feedback": None,
            "assistant_message": "승인되었습니다. 저장용 payload를 생성합니다.",
        }

    return {
        "approval_status": "revision_requested",
        "approval_feedback": user_input,
        "assistant_message": "초안을 수정하겠습니다. 추가하거나 바꾸고 싶은 내용을 입력해 주세요.",
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