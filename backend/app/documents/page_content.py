import json
from pathlib import Path

from app.documents.background import parsed_text_path
from app.models import Document


def _document_dir(document: Document) -> Path:
    return Path(document.storage_path).parent


def load_pages(document: Document) -> list[dict]:
    """Returns the cached [{"page_number": int, "text": str}, ...] list produced during
    parsing, or [] if the parsed cache is missing (e.g. document still processing)."""
    path = parsed_text_path(_document_dir(document))
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_page(document: Document, page_number: int) -> dict | None:
    for page in load_pages(document):
        if page.get("page_number") == page_number:
            return page
    return None


def find_highlight_offsets(page_text: str, chunk_text: str | None) -> tuple[int, int] | None:
    """Locate where `chunk_text` sits within `page_text`, tolerating the whitespace
    normalization that chunking can introduce. Returns (start, end) or None if it can't
    be located (still show the page, just without a highlight)."""
    if not chunk_text:
        return None

    idx = page_text.find(chunk_text)
    if idx != -1:
        return (idx, idx + len(chunk_text))

    # Fall back to anchoring on the chunk's opening words — chunking/whitespace
    # normalization can shift exact boundaries even though the content is the same.
    anchor = chunk_text.strip()[:120]
    if len(anchor) < 20:
        return None
    idx = page_text.find(anchor)
    if idx != -1:
        return (idx, idx + len(anchor))

    return None
