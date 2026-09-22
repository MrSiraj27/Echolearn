"""Vector store backed by Qdrant Cloud instead of local Chroma — used when QDRANT_URL is
set (see app/rag/vectorstore_select.py). Kept at full feature parity with vectorstore.py
(chromadb-backed): tabular-query boosting, multi-document retrieval, and get_all_chunks.
"""
import re
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.rag.embeddings import get_embeddings

COLLECTION_NAME = "echolearn_docs"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size

_TABULAR_QUERY_PATTERN = re.compile(
    r"\b(how much|how many|total|revenue|profit|expense|budget|percentage|percent|"
    r"average|sum|price|cost|rate|amount|figure|number of|compare|comparison|"
    r"vs\.?|versus)\b|\d",
    re.IGNORECASE,
)


def _looks_tabular(query: str) -> bool:
    return bool(_TABULAR_QUERY_PATTERN.search(query))


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
        )
        # Qdrant Cloud (unlike local/in-memory mode) refuses to filter on a payload field
        # that has no index, so every field used in a query_filter/scroll_filter above
        # needs one created up front.
        for field in ("user_id", "document_id", "chunk_type"):
            client.create_payload_index(
                collection_name=COLLECTION_NAME, field_name=field, field_schema=qmodels.PayloadSchemaType.KEYWORD
            )
    return client


def add_chunks(document_id: uuid.UUID, user_id: uuid.UUID, chunks: list[dict]) -> None:
    if not chunks:
        return

    client = get_client()
    texts = [c["text"] for c in chunks]
    embeddings = get_embeddings(texts)

    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={**chunk["metadata"], "text": text},
        )
        for text, embedding, chunk in zip(texts, embeddings, chunks)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def _points_to_chunks(points) -> list[dict]:
    return [
        {
            "text": point.payload.get("text", ""),
            "metadata": {k: v for k, v in point.payload.items() if k != "text"},
            "distance": 1 - point.score,  # cosine similarity -> distance, to match chroma's shape
        }
        for point in points
    ]


def _query(
    client: QdrantClient,
    query_embedding: list[float],
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    top_k: int,
    chunk_type: str | None = None,
) -> list[dict]:
    if top_k <= 0:
        return []

    must = [
        qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=str(user_id))),
        qmodels.FieldCondition(key="document_id", match=qmodels.MatchAny(any=[str(d) for d in document_ids])),
    ]
    if chunk_type:
        must.append(qmodels.FieldCondition(key="chunk_type", match=qmodels.MatchValue(value=chunk_type)))

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=qmodels.Filter(must=must),
        limit=top_k,
    ).points
    return _points_to_chunks(results)


def search(query: str, user_id: uuid.UUID, document_ids: list[uuid.UUID], top_k: int = 6) -> list[dict]:
    if not document_ids:
        return []

    client = get_client()
    query_embedding = get_embeddings([query])[0]

    if not _looks_tabular(query):
        return _query(client, query_embedding, user_id, document_ids, top_k)

    # Tabular-looking query: pull table chunks specifically (so they aren't crowded out by
    # semantically-closer prose) alongside the normal mixed search, then merge & de-dupe.
    table_k = max(top_k // 2, 4)
    table_chunks = _query(client, query_embedding, user_id, document_ids, table_k, chunk_type="table")
    general_chunks = _query(client, query_embedding, user_id, document_ids, top_k)

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
    """Two-stage retrieval for chats spanning several documents: top-`per_doc_k` chunks
    from EACH document individually, then merge every candidate and re-rank by distance."""
    if not document_ids:
        return []

    client = get_client()
    query_embedding = get_embeddings([query])[0]

    candidates: list[dict] = []
    for document_id in document_ids:
        candidates.extend(_query(client, query_embedding, user_id, [document_id], per_doc_k))

    candidates.sort(key=lambda c: c["distance"])
    return candidates[:top_k]


def get_all_chunks(document_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None) -> list[dict]:
    """Fetch every stored chunk for one document (or the union of several), in no
    particular order. Used for tasks that need broad document coverage rather than
    similarity to a single query — summarization, quiz generation."""
    client = get_client()
    ids = document_ids if document_ids else [document_id]
    doc_filter = qmodels.Filter(
        must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchAny(any=[str(d) for d in ids]))]
    )

    chunks: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=doc_filter,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for point in points:
            chunks.append(
                {
                    "text": point.payload.get("text", ""),
                    "metadata": {k: v for k, v in point.payload.items() if k != "text"},
                }
            )
        if offset is None:
            break
    return chunks


def delete_document(document_id: uuid.UUID) -> None:
    client = get_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=str(document_id)))]
            )
        ),
    )
