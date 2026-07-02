"""
파일명: manual_agent/ai_structurer.py

주요 기능:
- OpenAI API를 호출하는 파일
- 2개의 Agent 호출 함수를 제공한다.

구체적인 설명:
1. run_clarification_agent()
   - 사용자와 대화하면서 요청을 구체화한다.
   - 정보가 부족하면 추가 질문을 반환한다.
   - 정보가 충분하면 gathered_summary를 반환한다.

2. structure_request_with_ai()
   - 구체화된 요청을 받아 Markdown 섹션을 생성한다.
   - 기존 processor.py에서 그대로 사용한다.
"""

import json
from typing import Any

from manual_agent.config import OPENAI_MODEL, create_openai_client
from manual_agent.prompts import CLARIFICATION_AGENT_PROMPT, SYSTEM_PROMPT
from manual_agent.schema import (
    CLARIFICATION_OUTPUT_SCHEMA,
    STRUCTURED_OUTPUT_SCHEMA,
)


def run_clarification_agent(
    company_id: str,
    chat_messages: list[dict[str, str]],
) -> dict[str, Any]:
    client = create_openai_client()

    messages = [
        {
            "role": "system",
            "content": CLARIFICATION_AGENT_PROMPT,
        },
        {
            "role": "user",
            "content": f"companyId: {company_id}",
        },
        *chat_messages,
    ]

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "clarification_agent_result",
                "strict": True,
                "schema": CLARIFICATION_OUTPUT_SCHEMA,
            },
        },
    )

    content = completion.choices[0].message.content

    if content is None:
        raise RuntimeError("Clarification Agent 응답 content가 비어 있습니다.")

    return json.loads(content)


def structure_request_with_ai(request: dict[str, Any]) -> dict[str, Any]:
    client = create_openai_client()

    user_input = json.dumps(request, ensure_ascii=False)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"다음 요청을 기준으로 매뉴얼 보완용 Markdown 섹션을 생성해라:\n{user_input}",
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "manual_agent_structured_result",
                "strict": True,
                "schema": STRUCTURED_OUTPUT_SCHEMA,
            },
        },
    )

    content = completion.choices[0].message.content

    if content is None:
        raise RuntimeError("Markdown Section Agent 응답 content가 비어 있습니다.")

    return json.loads(content)