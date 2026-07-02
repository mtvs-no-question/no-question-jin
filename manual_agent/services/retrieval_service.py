"""
역할:
    기존 매뉴얼 검색 기능을 담당한다.

연결되는 파일:
    - manual_agent/nodes.py
        existing_manual_search_node에서 search_existing_manual()을 호출한다.
    - manual_agent/quality_checker.py
        검색된 기존 매뉴얼 context를 바탕으로 생성 초안과 충돌 여부를 검사할 수 있다.

현재 상태:
    MVP 단계에서는 실제 DB / VectorDB 검색을 하지 않는다.
    따라서 현재는 검색 조건을 출력하고 빈 배열을 반환한다.

나중에 교체할 부분:
    - VectorDB 검색
    - 기존 매뉴얼 DB 검색
    - 파일 기반 Markdown 검색
"""

from typing import Any


def search_existing_manual(
    company_id: str,
    product_model: str,
    issue_topic: str,
) -> list[dict[str, Any]]:
    print("\n[Existing Manual Search]")
    print(f"company_id={company_id}")
    print(f"product_model={product_model}")
    print(f"issue_topic={issue_topic}")

    return []