import re
import uuid
from functools import lru_cache

import chromadb

from app.core.config import settings
from app.rag.embeddings import get_embeddings

COLLECTION_NAME = "echolearn_docs"

_TABULAR_QUERY_PATTERN = re.compile(
    r"\b(how much|how many|total|revenue|profit|expense|budget|percentage|percent|"
    r"average|sum|price|cost|rate|amount|figure|number of|compare|comparison|"
    r"vs\.?|versus)\b|\d",
    re.IGNORECASE,
)


def _looks_tabular(query: str) -> bool:
    """Heuristic: does this question plausibly need numeric/tabular data? If so, boost
    table-type chunks in retrieval so a financial figure buried in a table isn't crowded
    out by more textually-similar prose chunks."""
    return bool(_TABULAR_QUERY_PATTERN.search(query))


@lru_cache(maxsize=1)
def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.CHROMA_PATH)


def get_collection():
    return get_client().get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def add_chunks(document_id: uuid.UUID, user_id: uuid.UUID, chunks: list[dict]) -> None:
    if not chunks:
        return

    collection = get_collection()
    texts = [c["text"] for c in chunks]
    embeddings = get_embeddings(texts)
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [c["metadata"] for c in chunks]

    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)


def _build_where(user_id: uuid.UUID, document_ids: list[uuid.UUID], chunk_type: str | None = None) -> dict:
    clauses = [
        {"user_id": {"$eq": str(user_id)}},
        {"document_id": {"$in": [str(d) for d in document_ids]}},
    ]
    if chunk_type:
        clauses.append({"chunk_type": {"$eq": chunk_type}})
    return {"$and": clauses}


def _run_query(collection, query_embedding: list[float], where: dict, n_results: int) -> list[dict]:
    if n_results <= 0:
        return []
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results, where=where)

    chunks: list[dict] = []
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    for text, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
        chunks.append({"text": text, "metadata": metadata, "distance": distance})

    return chunks


def search(query: str, user_id: uuid.UUID, document_ids: list[uuid.UUID], top_k: int = 6) -> list[dict]:
    if not document_ids:
        return []

    collection = get_collection()
    query_embedding = get_embeddings([query])[0]

    if not _looks_tabular(query):
        return _run_query(collection, query_embedding, _build_where(user_id, document_ids), top_k)

    # Tabular-looking query: pull table chunks specifically (so they aren't crowded out by
    # semantically-closer prose) alongside the normal mixed search, then merge & de-dupe.
    table_k = max(top_k // 2, 4)
    table_chunks = _run_query(collection, query_embedding, _build_where(user_id, document_ids, "table"), table_k)
    general_chunks = _run_query(collection, query_embedding, _build_where(user_id, document_ids), top_k)

    seen: set[str] = set()
    merged: list[dict] = []
    for chunk in table_chunks + general_chunks:
        if chunk["text"] not in seen:
            seen.add(chunk["text"])
            merged.append(chunk)

    merged.sort(key=lambda c: c["distance"])
    return merged[: table_k + top_k]


def search_multi_document(
    query: str,
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    top_k: int = 8,
    per_doc_k: int = 3,
) -> list[dict]:
    """Two-stage retrieval for chats spanning several documents (workspaces, multi-doc
    folders): a flat top-k search over all documents combined can let one large/dominant
    document crowd out smaller ones. Instead, retrieve top-`per_doc_k` chunks from EACH
    document individually (stage 1), then merge every candidate and re-rank by distance,
    taking the overall best `top_k` for the final context (stage 2)."""
    if not document_ids:
        return []

    collection = get_collection()
    query_embedding = get_embeddings([query])[0]

    candidates: list[dict] = []
    for document_id in document_ids:
        where = _build_where(user_id, [document_id])
        candidates.extend(_run_query(collection, query_embedding, where, per_doc_k))

    candidates.sort(key=lambda c: c["distance"])
    return candidates[:top_k]


def get_all_chunks(document_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None) -> list[dict]:
    """Fetch every stored chunk for one document (or the union of several), in no
    particular order. Used for tasks that need broad document coverage rather than
    similarity to a single query — summarization, quiz generation."""
    collection = get_collection()
    ids = document_ids if document_ids else [document_id]
    where = {"document_id": {"$in": [str(d) for d in ids]}} if len(ids) > 1 else {"document_id": {"$eq": str(ids[0])}}

    results = collection.get(where=where, include=["documents", "metadatas"])

    chunks: list[dict] = []
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    for text, metadata in zip(documents, metadatas):
        chunks.append({"text": text, "metadata": metadata})
    return chunks


def delete_document(document_id: uuid.UUID) -> None:
    collection = get_collection()
    collection.delete(where={"document_id": {"$eq": str(document_id)}})
