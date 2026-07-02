# manual_agent 구조

## llm
OpenAI 호출, 프롬프트, JSON Schema 관리

## workflow
LangGraph State, Node, Graph 정의

## services
기존 매뉴얼 검색, 품질 검수, 승인 처리

## storage
DB / VectorDB / GraphDB 저장 payload 생성 및 sink 처리

## processor.py
기존 MVP 처리 흐름. LangGraph 전환 후 점진적으로 축소 예정