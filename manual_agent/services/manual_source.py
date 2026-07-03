"""
파일명:
    manual_agent/services/manual_source.py

역할:
    사용자가 입력한 제품 매뉴얼 파일 경로를 읽어 LLM에 전달할 manual_context를 만든다.

연결되는 파일:
    - manual_agent/workflow/nodes.py
        manual_context_load_node에서 load_manual_context()를 호출한다.
    - manual_agent/workflow/graph.py
        manual_source_choice_node 이후, 파일 사용 여부에 따라 manual_context_load_node로 분기한다.

지원 파일:
    - .txt
    - .md
    - .pdf

주의:
    PDF는 텍스트 추출 가능한 PDF만 지원한다.
    스캔본 PDF는 OCR이 필요하므로 현재 MVP에서는 지원하지 않는다.
"""

from pathlib import Path

from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def load_manual_context(file_path: str, max_chars: int = 12000) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"매뉴얼 파일을 찾을 수 없습니다: {file_path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {extension}. "
            "지원 형식은 .pdf, .md, .txt 입니다."
        )

    if extension in [".txt", ".md"]:
        text = path.read_text(encoding="utf-8", errors="ignore")

    elif extension == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text)

        text = "\n\n".join(pages)

    else:
        text = ""

    text = text.strip()

    if not text:
        raise ValueError("파일에서 텍스트를 추출하지 못했습니다.")

    return text[:max_chars]