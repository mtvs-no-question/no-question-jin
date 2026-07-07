"""
파일명:
    web_app.py

역할:
    브라우저에서 manual_agent를 실행할 수 있도록 FastAPI 서버와 정적 프론트엔드를 제공한다.

연결되는 파일:
    - manual_agent/runtime/runner.py
        LangGraph 실행, interrupt 추출, resume 처리를 담당한다.
    - manual_agent/workflow/graph.py
        runner.py를 통해 graph를 생성한다.
    - web_frontend/index.html
        실제 채팅 화면이다.
    - web_frontend/app.js
        /api/chat, /api/resume, /api/upload API를 호출한다.

실행 방법:
    uv add fastapi uvicorn python-multipart
    uv run --active uvicorn web_app:app --reload --host 127.0.0.1 --port 8080

브라우저:
    http://127.0.0.1:8080

주의:
    이 서버는 로컬 MVP용이다.
    운영 환경에서는 사용자 인증, 권한, DB 저장, 영구 checkpointer를 추가해야 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from manual_agent.runtime.runner import (
    DEFAULT_COMPANY_ID,
    build_state,
    create_graph_for_local_server,
    invoke_graph,
    resume_graph,
)


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "web_frontend"
UPLOAD_DIR = BASE_DIR / "runtime_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".md", ".txt"}

app = FastAPI(title="No Question Jin Manual Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

GRAPH = create_graph_for_local_server()

# 로컬 MVP용 세션 저장소다. 서버를 재시작하면 초기화된다.
SESSIONS: dict[str, dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str | None = None
    company_id: str = DEFAULT_COMPANY_ID


class ResumeRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    resume: str = Field(min_length=1)
    company_id: str = DEFAULT_COMPANY_ID


@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(status_code=404, detail="web_frontend/index.html 파일이 없습니다.")

    return FileResponse(index_path)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "manual-agent-web",
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    thread_id = request.thread_id or f"thread-{uuid4().hex}"
    session = _get_or_create_session(thread_id=thread_id, company_id=request.company_id)

    user_message = {
        "role": "user",
        "content": request.message.strip(),
    }
    session["chat_messages"].append(user_message)

    state = build_state(
        company_id=request.company_id,
        conversation_id=thread_id,
        chat_messages=session["chat_messages"],
    )

    try:
        response, raw_result = invoke_graph(
            graph=GRAPH,
            state=state,
            thread_id=thread_id,
            company_id=request.company_id,
        )
    except Exception as error:
        return _error_response(thread_id=thread_id, error=error)

    _sync_session_after_result(session=session, response=response, raw_result=raw_result)

    return response


@app.post("/api/resume")
def resume(request: ResumeRequest):
    session = _get_or_create_session(thread_id=request.thread_id, company_id=request.company_id)

    try:
        response, raw_result = resume_graph(
            graph=GRAPH,
            thread_id=request.thread_id,
            company_id=request.company_id,
            resume_value=request.resume.strip(),
        )
    except Exception as error:
        return _error_response(thread_id=request.thread_id, error=error)

    if response.get("approval_status") == "revision_requested":
        session["chat_messages"].append(
            {
                "role": "user",
                "content": f"이전 초안 수정 요청: {request.resume.strip()}",
            }
        )

    _sync_session_after_result(session=session, response=response, raw_result=raw_result)

    return response


@app.post("/api/upload")
async def upload_manual(thread_id: str, file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="지원 파일 형식은 PDF, MD, TXT입니다.",
        )

    safe_name = Path(file.filename or f"manual{suffix}").name
    stored_name = f"{thread_id}_{uuid4().hex}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name

    content = await file.read()
    stored_path.write_bytes(content)

    return {
        "file_name": safe_name,
        "file_path": str(stored_path.resolve()),
        "size": len(content),
    }


def _get_or_create_session(thread_id: str, company_id: str) -> dict[str, Any]:
    if thread_id not in SESSIONS:
        SESSIONS[thread_id] = {
            "thread_id": thread_id,
            "company_id": company_id,
            "chat_messages": [],
        }

    return SESSIONS[thread_id]


def _sync_session_after_result(
    *,
    session: dict[str, Any],
    response: dict[str, Any],
    raw_result: dict[str, Any],
) -> None:
    assistant_message = response.get("message") or raw_result.get("assistant_message")

    if assistant_message and response.get("status") != "interrupted":
        last = session["chat_messages"][-1] if session["chat_messages"] else None

        if not last or last.get("role") != "assistant" or last.get("content") != assistant_message:
            session["chat_messages"].append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )


def _error_response(thread_id: str, error: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "thread_id": thread_id,
        "message": "실행 중 오류가 발생했습니다. 서버 터미널 로그를 확인해 주세요.",
        "error": str(error),
    }
