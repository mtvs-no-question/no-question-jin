# No Question Jin Web Frontend Patch

## 추가되는 파일

```text
web_app.py
web_frontend/index.html
web_frontend/styles.css
web_frontend/app.js
manual_agent/runtime/__init__.py
manual_agent/runtime/runner.py
```

## 설치

```cmd
uv add fastapi uvicorn python-multipart
```

## 실행

```cmd
uv run --active uvicorn web_app:app --reload --host 127.0.0.1 --port 8080
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8080
```

## 동작 방식

- `/api/chat`: 새 사용자 메시지로 graph 실행
- `/api/resume`: interrupt 이후 사용자 응답으로 graph 재개
- `/api/upload`: PDF/MD/TXT 파일 업로드 후 서버 로컬 경로 반환

## 주의

- 이 패치는 로컬 MVP용입니다.
- 운영 환경에서는 인증, 권한, DB 저장, 영구 checkpointer, 파일 보안 검사가 필요합니다.
- `web_app.py`는 서버 재시작 시 세션 메모리가 초기화됩니다.
