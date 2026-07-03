"""
파일명:
    manual_agent/llm/ai_structurer.py

역할:
    LLM을 호출해 Clarification Agent와 Markdown Section Agent를 실행한다.

연결되는 파일:
    - manual_agent/config.py
        chat_completion()을 호출한다.
        OpenAI API 또는 OpenAI-compatible 로컬 서버 설정은 config.py가 담당한다.
    - manual_agent/llm/prompts.py
        CLARIFICATION_AGENT_PROMPT, SYSTEM_PROMPT를 사용한다.
    - manual_agent/llm/schema.py
        CLARIFICATION_OUTPUT_SCHEMA, STRUCTURED_OUTPUT_SCHEMA를 사용한다.
    - manual_agent/workflow/nodes.py
        run_clarification_agent(), structure_request_with_ai()를 호출한다.

설계 의도:
    이 파일에서는 모델명, base_url, api_key를 직접 다루지 않는다.
    모델 교체는 .env에서만 처리한다.

주의:
    로컬 Qwen처럼 json_schema 강제가 약한 모델은 JSON을 깨뜨릴 수 있다.
    따라서 JSON 파싱 실패 시 json-repair로 복구를 시도한다.
"""

import json
from pathlib import Path
from typing import Any

from manual_agent.config import chat_completion
from manual_agent.llm.prompts import CLARIFICATION_AGENT_PROMPT, SYSTEM_PROMPT
from manual_agent.llm.schema import (
    CLARIFICATION_OUTPUT_SCHEMA,
    STRUCTURED_OUTPUT_SCHEMA,
)


def _parse_json_content(content: str) -> dict[str, Any]:
    """
    역할:
        LLM 응답 문자열을 JSON dict로 변환한다.

    처리 순서:
        1. ```json 코드블록 제거
        2. 첫 번째 { 부터 마지막 } 까지만 추출
        3. json.loads() 시도
        4. 실패하면 json-repair로 복구 시도
        5. 그래도 실패하면 원본 응답을 debug_last_llm_response.txt에 저장
    """

    cleaned = content.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")

    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        cleaned = cleaned[first_brace : last_brace + 1]

    try:
        parsed = json.loads(cleaned)

    except json.JSONDecodeError as original_error:
        try:
            from json_repair import repair_json

            repaired = repair_json(cleaned)
            parsed = json.loads(repaired)

        except Exception as repair_error:
            debug_path = Path("debug_last_llm_response.txt")
            debug_path.write_text(content, encoding="utf-8")

            raise RuntimeError(
                "LLM 응답을 JSON으로 파싱하지 못했습니다.\n"
                "원본 응답을 debug_last_llm_response.txt에 저장했습니다.\n\n"
                f"원본 응답 앞부분:\n{content[:1000]}"
            ) from repair_error

    if not isinstance(parsed, dict):
        raise RuntimeError(
            "LLM 응답 JSON이 dict 객체가 아닙니다.\n"
            f"응답 타입: {type(parsed)}"
        )

    return parsed


def run_clarification_agent(
    company_id: str,
    chat_messages: list[dict[str, str]],
) -> dict[str, Any]:
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

    completion = chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=2048,
        json_schema={
            "name": "clarification_agent_result",
            "strict": True,
            "schema": CLARIFICATION_OUTPUT_SCHEMA,
        },
    )

    content = completion.choices[0].message.content

    if content is None:
        raise RuntimeError("Clarification Agent 응답 content가 비어 있습니다.")

    return _parse_json_content(content)


def structure_request_with_ai(request: dict[str, Any]) -> dict[str, Any]:
    user_input = json.dumps(request, ensure_ascii=False)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "다음 요청을 기준으로 매뉴얼 보완용 Markdown 섹션을 생성해라.\n\n"
                "반드시 JSON 객체만 출력하라.\n"
                "마크다운 코드블록을 쓰지 마라.\n"
                "JSON 밖에 설명 문장을 쓰지 마라.\n"
                "응답의 첫 글자는 반드시 { 이어야 한다.\n\n"
                f"{user_input}"
            ),
        },
    ]

    completion = chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=4096,
        json_schema={
            "name": "manual_agent_structured_result",
            "strict": True,
            "schema": STRUCTURED_OUTPUT_SCHEMA,
        },
    )

    content = completion.choices[0].message.content

    if content is None:
        raise RuntimeError("Markdown Section Agent 응답 content가 비어 있습니다.")

    return _parse_json_content(content)