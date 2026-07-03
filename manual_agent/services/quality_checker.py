"""
역할:
    Markdown Section Agent가 생성한 매뉴얼 초안을 검수한다.

연결되는 파일:
    - manual_agent/nodes.py
        quality_check_node에서 check_manual_section()을 호출한다.
    - manual_agent/retrieval_service.py
        기존 매뉴얼 검색 결과와 생성 초안을 비교할 때 existing_manual_context를 사용한다.

현재 검수 기준:
    - 제품 모델명 존재 여부
    - 섹션 제목 존재 여부
    - Markdown 본문 존재 여부
    - missing_fields 존재 여부

확장 방향:
    - 기존 매뉴얼과 중복 여부 검사
    - 기존 매뉴얼과 내용 충돌 여부 검사
    - 사용자가 말하지 않은 기능을 AI가 지어냈는지 검사
    - LLM 기반 품질 검수 추가
"""

from typing import Any


def check_manual_section(
    structured_result: dict[str, Any] | None,
    existing_manual_context: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    역할:
        Markdown Section Agent가 생성한 매뉴얼 초안을 검수한다.

    연결되는 파일:
        - manual_agent/workflow/nodes.py
            quality_check_node에서 호출한다.

    핵심:
        structured_result가 None이면 에러를 내지 않고 검수 실패로 반환한다.
    """

    if structured_result is None:
        return {
            "passed": False,
            "missing": ["draft_result"],
            "reason": "생성된 초안이 없어 품질 검수를 진행할 수 없습니다.",
        }

    missing = []

    product = structured_result.get("product", {})
    manual_section = structured_result.get("manual_section", {})

    if not product.get("model_name"):
        missing.append("product.model_name")

    if not manual_section.get("section_title"):
        missing.append("manual_section.section_title")

    if not manual_section.get("markdown"):
        missing.append("manual_section.markdown")

    if structured_result.get("missing_fields"):
        missing.extend(structured_result["missing_fields"])

    return {
        "passed": len(missing) == 0,
        "missing": missing,
        "reason": "기본 필드 검수 통과" if not missing else "필수 필드 누락",
    }