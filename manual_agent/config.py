"""
파일명: manual_agent/config.py

주요 기능:
- 환경변수 로드
- OpenAI API Key 및 모델명 설정
- OpenAI Client 생성 함수 제공

구체적인 설명:
- .env 파일에서 OPENAI_API_KEY와 OPENAI_MODEL을 읽는다.
- OPENAI_MODEL 값이 없으면 기본값으로 gpt-4o-mini를 사용한다.
- create_openai_client()는 OpenAI 호출이 필요한 파일에서 가져다 쓴다.
- API Key가 없으면 실행 초기에 명확한 에러를 발생시킨다.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def create_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 .env에 없습니다.")

    return OpenAI(api_key=OPENAI_API_KEY)