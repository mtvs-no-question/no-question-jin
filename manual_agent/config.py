"""
파일명:
    manual_agent/config.py

역할:
    LLM 연결 설정을 한 곳에서 관리한다.

연결되는 파일:
    - manual_agent/llm/ai_structurer.py
        chat_completion()을 호출해 LLM 응답을 받는다.
    - .env
        LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_EXTRA_BODY,
        LLM_USE_JSON_SCHEMA 값을 읽는다.

설계 의도:
    OpenAI API와 OpenAI-compatible 로컬 서버를 코드 수정 없이 전환한다.
    이후에는 .env의 모델명, base_url만 바꾸면 된다.

호환성:
    기존 코드에서 OPENAI_MODEL, create_openai_client를 import하던 경우도
    깨지지 않도록 OPENAI_MODEL 별칭을 유지한다.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

try:
    from langsmith.wrappers import wrap_openai
except ImportError:
    wrap_openai = None


load_dotenv()

LLM_TOKEN_PARAM = os.getenv("LLM_TOKEN_PARAM", "max_tokens").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "")).strip()
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip()
LLM_EXTRA_BODY = os.getenv("LLM_EXTRA_BODY", "").strip()
LLM_USE_JSON_SCHEMA = (
    os.getenv("LLM_USE_JSON_SCHEMA", "true").strip().lower()
    in ["true", "1", "yes", "y"]
)

# 기존 코드 호환용 별칭
OPENAI_MODEL = LLM_MODEL


def create_openai_client() -> OpenAI:
    """
    역할:
        OpenAI 또는 OpenAI-compatible 서버용 client를 생성한다.

    동작:
        - LLM_BASE_URL이 있으면 로컬 Qwen / llama-server 같은 호환 서버로 요청한다.
        - LLM_BASE_URL이 비어 있으면 기본 OpenAI API로 요청한다.
    """

    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY 또는 OPENAI_API_KEY가 .env에 없습니다.")

    if LLM_BASE_URL:
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )
    else:
        client = OpenAI(
            api_key=LLM_API_KEY,
        )

    if wrap_openai is not None:
        return wrap_openai(client)

    return client


def get_extra_body() -> dict[str, Any] | None:
    """
    역할:
        로컬 LLM 서버에 전달할 extra_body 설정을 읽는다.

    예:
        LLM_EXTRA_BODY={"chat_template_kwargs":{"thinking":false}}
    """

    if not LLM_EXTRA_BODY:
        return None

    try:
        return json.loads(LLM_EXTRA_BODY)
    except json.JSONDecodeError as error:
        raise ValueError("LLM_EXTRA_BODY는 올바른 JSON 문자열이어야 합니다.") from error


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 2048,
    json_schema: dict[str, Any] | None = None,
):
    """
    역할:
        프로젝트 전체에서 사용할 공통 LLM 호출 함수다.

    핵심:
        - 모델명, base_url, api_key, extra_body를 여기서만 관리한다.
        - 서버별 토큰 파라미터 차이를 LLM_TOKEN_PARAM으로 처리한다.
        - max_tokens가 거부되면 max_completion_tokens로 한 번 재시도한다.
    """

    client = create_openai_client()

    request_messages = list(messages)

    if json_schema and not LLM_USE_JSON_SCHEMA:
        schema_text = json.dumps(json_schema, ensure_ascii=False, indent=2)

        request_messages.append(
            {
                "role": "user",
                "content": (
                    "반드시 아래 JSON Schema에 맞는 JSON 객체만 출력하라.\n"
                    "설명 문장, 인사말, 마크다운 코드블록을 절대 쓰지 마라.\n"
                    "응답의 첫 글자는 반드시 { 이어야 한다.\n\n"
                    f"JSON Schema:\n{schema_text}"
                ),
            }
        )

    kwargs: dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": request_messages,
        "temperature": temperature,
    }

    token_param = LLM_TOKEN_PARAM

    if token_param not in ["max_tokens", "max_completion_tokens"]:
        raise ValueError(
            "LLM_TOKEN_PARAM은 max_tokens 또는 max_completion_tokens만 사용할 수 있습니다."
        )

    kwargs[token_param] = max_tokens

    extra_body = get_extra_body()
    if extra_body:
        kwargs["extra_body"] = extra_body

    if json_schema and LLM_USE_JSON_SCHEMA:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": json_schema,
        }

    try:
        return client.chat.completions.create(**kwargs)

    except BadRequestError as error:
        error_message = str(error)

        if (
            token_param == "max_tokens"
            and "max_tokens" in error_message
            and "max_completion_tokens" in error_message
        ):
            retry_kwargs = dict(kwargs)
            retry_kwargs.pop("max_tokens", None)
            retry_kwargs["max_completion_tokens"] = max_tokens

            return client.chat.completions.create(**retry_kwargs)

        raise