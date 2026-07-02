"""
역할:
    로컬 CLI 실행 진입점이다.

연결되는 파일:
    - manual_agent/workflow/graph.py
        build_manual_agent_graph()를 호출해 LangGraph 워크플로우를 생성한다.
    - manual_agent/workflow/state.py
        graph.invoke()에 전달할 초기 state 구조를 맞춘다.

수정 이유:
    사용자가 초안을 승인하지 않은 경우 프로그램을 종료하지 않고
    추가 수정 내용을 입력받도록 대화 루프를 계속 유지한다.
"""

from manual_agent.workflow.graph import build_manual_agent_graph

COMPANY_ID = "019f1b62-dd8f-77f9-8500-22881b24065f"


def run_chat_loop():
    graph = build_manual_agent_graph()
    chat_messages: list[dict[str, str]] = []

    while True:
        user_input = input("\nUser > ").strip()

        if user_input in ["exit", "quit"]:
            break

        chat_messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        state = {
            "company_id": COMPANY_ID,
            "conversation_id": "local-conversation",
            "chat_messages": chat_messages,
            "existing_manual_context": [],
            "approval_status": "pending",
            "approval_feedback": None,
            "vector_payload": [],
        }

        result = graph.invoke(state)

        assistant_message = result.get("assistant_message")
        if assistant_message:
            print(f"\nAssistant > {assistant_message}")
            chat_messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

        if not result.get("is_ready"):
            continue

        quality = result.get("quality_result")
        if quality and not quality["passed"]:
            print("\n=== 품질 검수 실패 ===")
            print(quality)
            continue

        approval_status = result.get("approval_status")

        if approval_status == "revision_requested":
            feedback = result.get("approval_feedback")

            if feedback and feedback not in ["아니", "no", "reject", "rejected"]:
                chat_messages.append(
                    {
                        "role": "user",
                        "content": f"이전 초안 수정 요청: {feedback}",
                    }
                )

            continue

        if approval_status == "approved":
            draft = result.get("draft_result")

            if draft:
                print("\n=== 최종 Markdown ===")
                print(draft["manual_section"]["markdown"])

            break


if __name__ == "__main__":
    run_chat_loop()