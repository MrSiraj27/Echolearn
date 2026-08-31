"""Drop-in replacement for vectorstore.py backed by Qdrant Cloud instead of local Chroma.

To switch: set QDRANT_URL and QDRANT_API_KEY env vars, add `qdrant-client` to
requirements.txt, and change imports from `app.rag.vectorstore` to
`app.rag.vectorstore_qdrant` in background.py, routes.py, and langgraph_pipeline.py.
"""
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.rag.embeddings import get_embeddings

COLLECTION_NAME = "echolearn_docs"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
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


def search(query: str, user_id: uuid.UUID, document_ids: list[uuid.UUID], top_k: int = 6) -> list[dict]:
    if not document_ids:
        return []

    client = get_client()
    query_embedding = get_embeddings([query])[0]

    query_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=str(user_id))),
            qmodels.FieldCondition(
                key="document_id", match=qmodels.MatchAny(any=[str(d) for d in document_ids])
            ),
        ]
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=query_filter,
        limit=top_k,
    ).points

    return [
        {
            "text": point.payload.get("text", ""),
            "metadata": {k: v for k, v in point.payload.items() if k != "text"},
            "distance": 1 - point.score,  # cosine similarity -> distance, to match chroma's shape
        }
        for point in results
    ]


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
