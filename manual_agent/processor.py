"""
파일명: manual_agent/processor.py

주요 기능:
- Agent 전체 실행 흐름을 조립하는 중앙 처리 파일

구체적인 설명:
- OpenAI 구조화 함수를 호출한다.
- 구조화 결과에서 필수값 누락 여부를 검증한다.
- DB / VectorDB / GraphDB payload를 생성한다.
- sink를 통해 저장 또는 출력을 수행한다.
- main.py는 이 파일의 process_request()만 호출하면 된다.
"""

from typing import Any
from uuid import uuid4

from manual_agent.llm.ai_structurer import structure_request_with_ai
from manual_agent.storage.payload_builder import (
    build_db_payload,
    build_graph_payload,
    build_vector_payload,
)


def validate_structured_result(structured: dict[str, Any]) -> list[str]:
    missing_fields = list(structured.get("missing_fields", []))

    if not structured.get("company_id"):
        missing_fields.append("company_id")

    product = structured.get("product") or {}
    if not product.get("model_name"):
        missing_fields.append("product.model_name")

    return list(set(missing_fields))


def process_request(request: dict[str, Any], sink: Any) -> dict[str, Any]:
    job_id = str(uuid4())

    structured = structure_request_with_ai(request)

    missing_fields = validate_structured_result(structured)

    if missing_fields:
        return {
            "status": "failed",
            "job_id": job_id,
            "reason": "missing_required_fields",
            "missing_fields": missing_fields,
            "structured": structured,
        }

    db_payload = build_db_payload(job_id, request, structured)
    vector_payload = build_vector_payload(job_id, structured)
    graph_payload = build_graph_payload(job_id, structured)

    sink.save_db_payload(db_payload)
    sink.save_vector_payload(vector_payload)
    sink.save_graph_payload(graph_payload)

    return {
        "status": "success",
        "job_id": job_id,
        "structured": structured,
    }