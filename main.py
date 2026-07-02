"""
파일명: main.py

주요 기능:
- 로컬에서 2단계 Agent 흐름을 실행한다.

구체적인 설명:
1. Clarification Agent
   - 사용자와 터미널에서 계속 대화한다.
   - 사용자가 어떤 내용을 매뉴얼에 추가하고 싶은지 구체화한다.

2. Markdown Section Agent
   - 구체화가 끝나면 gathered_summary를 받아 Markdown 섹션을 생성한다.
   - 기존 processor.py를 그대로 사용한다.

현재 저장 방식:
- PrintSink를 사용한다.
- DB / VectorDB / GraphDB에는 실제 저장하지 않고 출력만 한다.
"""

from manual_agent.ai_structurer import run_clarification_agent
from manual_agent.processor import process_request
from manual_agent.sink import PrintSink, pretty_print


COMPANY_ID = "019f1b62-dd8f-77f9-8500-22881b24065f"


def run_chat_loop() -> None:
    sink = PrintSink()
    chat_messages: list[dict[str, str]] = []

    print("\n매뉴얼 보완 요청 구체화 Agent를 시작합니다.")
    print("종료하려면 exit 입력\n")

    while True:
        user_text = input("사용자: ").strip()

        if user_text.lower() in ["exit", "quit"]:
            print("종료합니다.")
            break

        if not user_text:
            continue

        chat_messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        clarification_result = run_clarification_agent(
            company_id=COMPANY_ID,
            chat_messages=chat_messages,
        )

        assistant_message = clarification_result["assistant_message"]

        print(f"\n구체화 Agent: {assistant_message}\n")

        chat_messages.append(
            {
                "role": "assistant",
                "content": assistant_message,
            }
        )

        if not clarification_result["is_ready"]:
            continue

        gathered_summary = clarification_result["gathered_summary"]

        if not gathered_summary:
            print("구체화된 요약이 없어 Markdown 섹션 생성을 중단합니다.")
            break

        final_request = {
            "companyId": COMPANY_ID,
            "user_prompt": gathered_summary,
        }

        pretty_print("FINAL REQUEST FOR MARKDOWN AGENT", final_request)

        result = process_request(final_request, sink)

        pretty_print("FINAL RESULT", result)

        manual_section = result.get("structured", {}).get("manual_section")

        if manual_section and manual_section.get("markdown"):
            print("\n[생성된 Markdown 섹션]")
            print(manual_section["markdown"])

        break


if __name__ == "__main__":
    run_chat_loop()