import json
import re
import uuid

AUDIO_CHUNK_CHAR_TARGET = 900


class _RecursiveCharacterTextSplitter:
    """A vendored copy of langchain_text_splitters.RecursiveCharacterTextSplitter's
    split_text (character-length, keep_separator=True, default separators), reimplemented
    here to avoid importing the langchain_text_splitters package: its __init__.py
    unconditionally imports SentenceTransformersTokenTextSplitter, which pulls in the full
    torch + transformers stack (400+MB RSS) just to reach this one class we actually use —
    a real problem on a memory-constrained host. Behavior verified to match upstream
    output exactly across representative inputs; see the class this replaces if upstream's
    algorithm ever needs to be re-synced."""

    def __init__(self, chunk_size: int, chunk_overlap: int, separators: list[str] | None = None):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = separators or ["\n\n", "\n", " ", ""]

    @staticmethod
    def _split_with_separator(text: str, separator: str) -> list[str]:
        if not separator:
            return list(text)
        # keep_separator=True: re-attach each separator to the text that follows it.
        pattern = f"({re.escape(separator)})"
        parts = re.split(pattern, text)
        merged = [parts[i] + parts[i + 1] for i in range(1, len(parts), 2)]
        if len(parts) % 2 == 0:
            merged += parts[-1:]
        merged = [parts[0], *merged]
        return [s for s in merged if s]

    def _merge_splits(self, splits: list[str]) -> list[str]:
        docs: list[str] = []
        current: list[str] = []
        total = 0
        for piece in splits:
            length = len(piece)
            if total + length > self._chunk_size:
                if current:
                    joined = "".join(current).strip()
                    if joined:
                        docs.append(joined)
                    while total > self._chunk_overlap or (total + length > self._chunk_size and total > 0):
                        total -= len(current[0])
                        current = current[1:]
            current.append(piece)
            total += length
        if current:
            joined = "".join(current).strip()
            if joined:
                docs.append(joined)
        return docs

    def _split(self, text: str, separators: list[str]) -> list[str]:
        separator = separators[-1]
        new_separators: list[str] = []
        for i, candidate in enumerate(separators):
            if not candidate:
                separator = candidate
                break
            if re.search(re.escape(candidate), text):
                separator = candidate
                new_separators = separators[i + 1 :]
                break

        splits = self._split_with_separator(text, separator)

        final_chunks: list[str] = []
        good_splits: list[str] = []
        for piece in splits:
            if len(piece) < self._chunk_size:
                good_splits.append(piece)
                continue
            if good_splits:
                final_chunks.extend(self._merge_splits(good_splits))
                good_splits = []
            if not new_separators:
                final_chunks.append(piece)
            else:
                final_chunks.extend(self._split(piece, new_separators))
        if good_splits:
            final_chunks.extend(self._merge_splits(good_splits))
        return final_chunks

    def split_text(self, text: str) -> list[str]:
        return self._split(text, self._separators)


_splitter = _RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


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
