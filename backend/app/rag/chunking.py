import json
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

AUDIO_CHUNK_CHAR_TARGET = 900


def chunk_text(
    pages: list[dict],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
) -> list[dict]:
    """Split parsed pages into overlapping chunks.

    `pages` is a list of {"page_number", "text", "tables", "start_time", "end_time"} dicts
    (as produced by the document parsers). Returns a list of {"text": str, "metadata": dict}
    dicts.

    Table blocks are never split by the text splitter — each table is embedded as one
    atomic chunk (tagged chunk_type="table") so a model answering a numeric question sees
    the whole table intact rather than a fragment of it.

    Audio/video transcript pages (identified by a non-null start_time) are grouped
    differently: consecutive short segments are merged into ~900-character chunks while
    tracking the timestamp range they span, so citations can point to a moment in the
    recording instead of a page number.
    """
    is_transcript = any(p.get("start_time") is not None for p in pages)
    if is_transcript:
        return _chunk_transcript(pages, document_id, user_id, filename)

    chunks: list[dict] = []

    for page in pages:
        page_text = page.get("text", "")
        if page_text.strip():
            for piece in _splitter.split_text(page_text):
                chunks.append(
                    {
                        "text": piece,
                        "metadata": {
                            "document_id": str(document_id),
                            "user_id": str(user_id),
                            "filename": filename,
                            "page_number": page.get("page_number"),
                            "chunk_type": "text",
                        },
                    }
                )

        for table in page.get("tables", []):
            markdown_table = table.get("markdown_table", "")
            if not markdown_table.strip():
                continue
            chunks.append(
                {
                    "text": markdown_table,
                    "metadata": {
                        "document_id": str(document_id),
                        "user_id": str(user_id),
                        "filename": filename,
                        "page_number": page.get("page_number"),
                        "chunk_type": "table",
                        "table_index": table.get("table_index", 0),
                        "table_json": json.dumps(table.get("json_table", [])),
                    },
                }
            )

    return chunks


def _chunk_transcript(
    pages: list[dict],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
) -> list[dict]:
    chunks: list[dict] = []
    buffer_texts: list[str] = []
    buffer_len = 0
    buffer_start: float | None = None
    buffer_end: float | None = None

    def flush():
        nonlocal buffer_texts, buffer_len, buffer_start, buffer_end
        if not buffer_texts:
            return
        chunks.append(
            {
                "text": " ".join(buffer_texts),
                "metadata": {
                    "document_id": str(document_id),
                    "user_id": str(user_id),
                    "filename": filename,
                    "chunk_type": "text",
                    "start_time_seconds": buffer_start,
                    "end_time_seconds": buffer_end,
                },
            }
        )
        buffer_texts = []
        buffer_len = 0
        buffer_start = None
        buffer_end = None

    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue

        if buffer_start is None:
            buffer_start = page.get("start_time")

        buffer_texts.append(text)
        buffer_len += len(text)
        buffer_end = page.get("end_time")

        if buffer_len >= AUDIO_CHUNK_CHAR_TARGET:
            flush()

    flush()
    return chunks
