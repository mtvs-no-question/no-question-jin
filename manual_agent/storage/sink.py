"""
파일명: manual_agent/sink.py

주요 기능:
- 저장 방식을 추상화하는 파일
- 현재는 print 출력만 수행

구체적인 설명:
- PrintSink는 DB 저장 대신 콘솔에 payload를 출력한다.
- 나중에 실제 DB, VectorDB, GraphDB가 연결되면 DatabaseSink 같은 클래스를 추가하면 된다.
- processor.py는 sink의 save_* 메서드만 호출하므로 저장 방식 교체가 쉽다.
"""

import json
from typing import Any


def pretty_print(title: str, data: Any) -> None:
    print(f"\n[{title}]")
    print(json.dumps(data, ensure_ascii=False, indent=2))


class PrintSink:
    def save_db_payload(self, payload: dict[str, Any]) -> None:
        pretty_print("DB PAYLOAD", payload)

    def save_vector_payload(self, payloads: list[dict[str, Any]]) -> None:
        pretty_print("VECTOR DB PAYLOAD", payloads)

    def save_graph_payload(self, payload: dict[str, Any]) -> None:
        pretty_print("GRAPH DB PAYLOAD", payload)


class DatabaseSink:
    """
    실제 DB 연결 시 사용할 자리.

    현재는 구현하지 않는다.
    나중에 DB 연결 방식이 확정되면 이 클래스 안의 pass를 실제 저장 로직으로 교체한다.
    """

    def save_db_payload(self, payload: dict[str, Any]) -> None:
        pass

    def save_vector_payload(self, payloads: list[dict[str, Any]]) -> None:
        pass

    def save_graph_payload(self, payload: dict[str, Any]) -> None:
        pass