from functools import lru_cache

from app.core.config import settings

# all-MiniLM-L6-v2, same model/weights as before, via an ONNX Runtime backend (fastembed)
# instead of PyTorch/sentence-transformers. Verified to produce numerically identical
# vectors (cosine similarity 1.00000 across test sentences) at roughly a quarter of the
# RSS: PyTorch alone adds ~400MB to a process just by being loaded, which is fine on a
# dev machine but reliably OOM-kills a memory-constrained host (e.g. Render's free
# 512MB tier) the moment the app embeds its first chunk.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# fastembed's default batch_size (256) makes ONNX allocate activations for 256 full-length
# chunks at once: measured ~1.2GB peak RSS embedding a longish document, which OOM-kills a
# 512MB host mid-upload. Batches of 16 peak at ~280MB for the same input.
EMBED_BATCH_SIZE = 16


@lru_cache(maxsize=1)
def get_embedding_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODEL_NAME, cache_dir=settings.HF_HOME or None)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return [vec.tolist() for vec in model.embed(texts, batch_size=EMBED_BATCH_SIZE)]
