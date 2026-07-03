"""
파일명:
    manual_agent/workflow/app.py

역할:
    LangSmith Studio / LangGraph API 서버가 불러올 graph 객체를 노출한다.

연결되는 파일:
    - manual_agent/workflow/graph.py
        build_manual_agent_graph()를 호출한다.
    - langgraph.json
        이 파일의 graph 변수를 참조한다.

중요:
    LangGraph API / Studio에서는 persistence를 서버가 자동으로 관리한다.
    따라서 여기서는 custom checkpointer인 InMemorySaver를 사용하지 않는다.
"""

from manual_agent.workflow.graph import build_manual_agent_graph


graph = build_manual_agent_graph(use_memory_checkpointer=False)