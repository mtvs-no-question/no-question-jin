"""
파일명: manual_agent/schema.py

주요 기능:
- OpenAI Agent들이 따라야 하는 JSON 응답 스키마 정의

구체적인 설명:
1. CLARIFICATION_OUTPUT_SCHEMA
   - 대화형 구체화 Agent의 응답 형식
   - 추가 질문이 필요한지, 다음 단계로 넘어가도 되는지 판단한다.

2. STRUCTURED_OUTPUT_SCHEMA
   - Markdown 섹션 작성 Agent의 응답 형식
   - DB / VectorDB / GraphDB payload 생성에 필요한 구조를 만든다.
"""


CLARIFICATION_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "company_id": {
            "type": ["string", "null"],
            "description": "고객사 ID",
        },
        "is_ready": {
            "type": "boolean",
            "description": "Markdown 작성 Agent로 넘길 준비가 되었는지 여부",
        },
        "assistant_message": {
            "type": "string",
            "description": "사용자에게 보여줄 대화 응답",
        },
        "gathered_summary": {
            "type": ["string", "null"],
            "description": "다음 Agent에게 넘길 구체화된 요청 요약",
        },
        "missing_questions": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "아직 사용자에게 확인해야 할 질문 목록",
        },
    },
    "required": [
        "company_id",
        "is_ready",
        "assistant_message",
        "gathered_summary",
        "missing_questions",
    ],
}


STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "company_id": {
            "type": ["string", "null"],
            "description": "고객사 ID",
        },
        "intent_type": {
            "type": "string",
            "enum": [
                "NEW_MANUAL",
                "NEW_MANUAL_FROM_REFERENCE",
                "MANUAL_UPDATE_FROM_INQUIRY",
                "UNKNOWN",
            ],
            "description": "사용자 요청 의도",
        },
        "product": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category": {
                    "type": ["string", "null"],
                    "description": "제품군. 예: air_conditioner",
                },
                "model_name": {
                    "type": ["string", "null"],
                    "description": "대상 제품 모델명",
                },
            },
            "required": ["category", "model_name"],
        },
        "reference_model": {
            "type": ["string", "null"],
            "description": "참조할 기존 모델명",
        },
        "issue_topic": {
            "type": ["string", "null"],
            "description": "수정 또는 보완이 필요한 주제",
        },
        "customer_context": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "age_group": {
                    "type": ["string", "null"],
                    "description": "고객 연령대",
                },
                "gender": {
                    "type": ["string", "null"],
                    "description": "고객 성별",
                },
                "customer_type": {
                    "type": ["string", "null"],
                    "description": "고객 유형",
                },
            },
            "required": ["age_group", "gender", "customer_type"],
        },
        "manual_task": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "task_summary": {
                    "type": "string",
                    "description": "요청을 한 문장으로 요약",
                },
                "required_action": {
                    "type": "string",
                    "description": "다음에 수행해야 할 작업",
                },
                "needs_existing_manual_search": {
                    "type": "boolean",
                    "description": "기존 매뉴얼 검색 필요 여부",
                },
                "should_save_to_vector_db": {
                    "type": "boolean",
                    "description": "현재 단계에서 VectorDB 저장 여부",
                },
            },
            "required": [
                "task_summary",
                "required_action",
                "needs_existing_manual_search",
                "should_save_to_vector_db",
            ],
        },
        "manual_section": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "description": "매뉴얼에 추가하거나 수정 제안할 Markdown 섹션",
            "properties": {
                "change_type": {
                    "type": "string",
                    "enum": [
                        "add_section",
                        "update_section",
                        "no_change_needed",
                    ],
                    "description": "섹션 변경 유형",
                },
                "section_title": {
                    "type": ["string", "null"],
                    "description": "추가 또는 수정할 섹션 제목",
                },
                "insert_after": {
                    "type": ["string", "null"],
                    "description": "어느 섹션 뒤에 삽입하면 좋은지",
                },
                "markdown": {
                    "type": ["string", "null"],
                    "description": "실제 매뉴얼에 삽입 가능한 Markdown 섹션",
                },
                "reason": {
                    "type": "string",
                    "description": "이 섹션이 필요한 이유",
                },
            },
            "required": [
                "change_type",
                "section_title",
                "insert_after",
                "markdown",
                "reason",
            ],
        },
        "missing_fields": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "처리에 필요한데 누락된 필드",
        },
    },
    "required": [
        "company_id",
        "intent_type",
        "product",
        "reference_model",
        "issue_topic",
        "customer_context",
        "manual_task",
        "manual_section",
        "missing_fields",
    ],
}