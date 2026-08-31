import os
from functools import lru_cache

from app.core.config import settings

if settings.HF_HOME:
    os.environ.setdefault("HF_HOME", settings.HF_HOME)

from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts, convert_to_numpy=True).tolist()
