"""
파일명: manual_agent/payload_builder.py

주요 기능:
- AI가 구조화한 결과를 저장용 payload로 변환

구체적인 설명:
- DB 저장용 payload를 만든다.
- VectorDB 저장용 payload를 만든다.
- GraphDB 저장용 payload를 만든다.
- 현재 MVP에서는 승인된 매뉴얼 본문이 없으므로 VectorDB payload는 기본적으로 빈 배열이다.
- 실제 DB 연결은 하지 않고, 저장에 필요한 데이터 형태만 만든다.
"""

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_db_payload(
    job_id: str,
    request: dict[str, Any],
    structured: dict[str, Any],
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "company_id": structured["company_id"],
        "intent_type": structured["intent_type"],
        "user_prompt": request["user_prompt"],
        "product_category": structured["product"]["category"],
        "product_model": structured["product"]["model_name"],
        "reference_model": structured["reference_model"],
        "issue_topic": structured["issue_topic"],
        "customer_context": structured["customer_context"],
        "task_summary": structured["manual_task"]["task_summary"],
        "required_action": structured["manual_task"]["required_action"],
        "needs_existing_manual_search": structured["manual_task"]["needs_existing_manual_search"],
        "manual_section": structured["manual_section"],
        "status": "structured",
        "created_at": now_iso(),
    }


def build_vector_payload(
    job_id: str,
    structured: dict[str, Any],
) -> list[dict[str, Any]]:
    if not structured["manual_task"]["should_save_to_vector_db"]:
        return []

    return [
        {
            "id": job_id,
            "text": structured["manual_task"]["task_summary"],
            "metadata": {
                "company_id": structured["company_id"],
                "product_model": structured["product"]["model_name"],
                "intent_type": structured["intent_type"],
            },
        }
    ]


def build_graph_payload(
    job_id: str,
    structured: dict[str, Any],
) -> dict[str, Any]:
    company_id = structured["company_id"]
    product_model = structured["product"]["model_name"]
    reference_model = structured["reference_model"]

    nodes = []
    edges = []

    if company_id:
        nodes.append(
            {
                "id": company_id,
                "type": "Company",
            }
        )

        edges.append(
            {
                "from": company_id,
                "to": job_id,
                "type": "REQUESTED_JOB",
            }
        )

    nodes.append(
        {
            "id": job_id,
            "type": "ManualJob",
            "intent_type": structured["intent_type"],
        }
    )

    if product_model:
        nodes.append(
            {
                "id": product_model,
                "type": "ProductModel",
            }
        )

        edges.append(
            {
                "from": job_id,
                "to": product_model,
                "type": "TARGETS_MODEL",
            }
        )

    if reference_model:
        nodes.append(
            {
                "id": reference_model,
                "type": "ProductModel",
            }
        )

        edges.append(
            {
                "from": job_id,
                "to": reference_model,
                "type": "BASED_ON_REFERENCE_MODEL",
            }
        )

    return {
        "job_id": job_id,
        "nodes": nodes,
        "edges": edges,
    }