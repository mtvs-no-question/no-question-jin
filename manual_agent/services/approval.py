"""
역할:
    생성된 매뉴얼 초안을 사람이 승인하거나 수정 요청하는 로컬 승인 단계를 담당한다.

연결되는 파일:
    - manual_agent/workflow/nodes.py
        approval_node에서 ask_approval()을 호출한다.
    - manual_agent/workflow/graph.py
        approval_status 값에 따라 payload 생성 단계로 갈지 종료할지 분기한다.
    - main.py
        revision_requested 상태면 사용자에게 추가 입력을 받고 대화를 계속한다.

현재 방식:
    CLI input()을 사용한다.

입력 규칙:
    - approve, approved, y, yes, 승인 → approved
    - 그 외 입력 → revision_requested
"""

from typing import Any


def ask_approval(draft_result: dict[str, Any]) -> dict[str, str | None]:
    markdown = draft_result["manual_section"]["markdown"]

    print("\n=== 생성된 매뉴얼 섹션 초안 ===")
    print(markdown)
    print("\n이 초안을 승인하시겠습니까?")
    print("승인하려면 approve 또는 승인 입력")
    print("수정하려면 수정할 내용을 그대로 입력하거나 아니라고 입력")

    user_input = input("approve / 수정내용 > ").strip()

    if user_input.lower() in ["approve", "approved", "y", "yes", "승인"]:
        return {
            "approval_status": "approved",
            "approval_feedback": None,
        }

    return {
        "approval_status": "revision_requested",
        "approval_feedback": user_input,
    }