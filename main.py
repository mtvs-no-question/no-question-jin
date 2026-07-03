"""
파일명:
    main.py

역할:
    로컬 CLI 실행 진입점이다.

연결되는 파일:
    - manual_agent/workflow/graph.py
        build_manual_agent_graph()를 호출해 LangGraph 워크플로우를 생성한다.
    - manual_agent/workflow/state.py
        graph.invoke()에 전달할 초기 state 구조를 맞춘다.
    - manual_agent/workflow/nodes.py
        graph 실행 중 각 node가 호출된다.

중요:
    graph.py에서 checkpointer=InMemorySaver()를 사용하므로,
    graph.invoke()를 호출할 때 반드시 config.configurable.thread_id를 전달해야 한다.

interrupt 처리:
    node에서 interrupt()가 발생하면 __interrupt__ 값을 확인하고,
    사용자 입력을 Command(resume=...)로 다시 graph에 전달한다.
"""

from langgraph.types import Command

from manual_agent.workflow.graph import build_manual_agent_graph


COMPANY_ID = "019f1b62-dd8f-77f9-8500-22881b24065f"
CONVERSATION_ID = "local-conversation"


def get_interrupt_payload(result: dict):
    interrupts = result.get("__interrupt__")

    if not interrupts:
        return None

    first_interrupt = interrupts[0]

    return getattr(first_interrupt, "value", first_interrupt)


def print_interrupt_payload(payload):
    print("\n=== 사용자 확인 필요 ===")

    if not isinstance(payload, dict):
        print(payload)
        return

    message = payload.get("message")
    markdown = payload.get("markdown")
    examples = payload.get("examples")
    options = payload.get("options")

    if message:
        print(message)

    if markdown:
        print("\n--- 초안 ---")
        print(markdown)

    if examples:
        print("\n예시:")
        for example in examples:
            print(f"- {example}")

    if options:
        print("\n선택지:")
        for option in options:
            print(f"- {option}")


def run_graph_with_interrupts(graph, state: dict, config: dict) -> dict:
    result = graph.invoke(state, config=config)

    while True:
        interrupt_payload = get_interrupt_payload(result)

        if not interrupt_payload:
            return result

        print_interrupt_payload(interrupt_payload)

        human_input = input("\n입력 > ").strip()

        result = graph.invoke(
            Command(resume=human_input),
            config=config,
        )


def run_chat_loop():
    graph = build_manual_agent_graph()
    chat_messages: list[dict[str, str]] = []

    config = {
        "configurable": {
            "thread_id": CONVERSATION_ID,
        },
        "tags": ["main-py", "local-cli", "manual-agent"],
        "metadata": {
            "company_id": COMPANY_ID,
            "conversation_id": CONVERSATION_ID,
            "entrypoint": "main.py",
        },
    }

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
            "conversation_id": CONVERSATION_ID,
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

        result = run_graph_with_interrupts(
            graph=graph,
            state=state,
            config=config,
        )

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