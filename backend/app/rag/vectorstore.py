"""Vector store selector: every other module imports from here (`app.rag.vectorstore`)
and gets whichever backend is configured, without needing to know which one it is.

- QDRANT_URL unset (default, local dev): local Chroma, persisted at CHROMA_PATH.
- QDRANT_URL set (typical for a deployed backend with an ephemeral filesystem, e.g.
  Render's free tier): Qdrant Cloud, so the vector index survives restarts/redeploys.

Both modules expose the same functions with the same shapes (see vectorstore_chroma.py /
vectorstore_qdrant.py), so this file is the only place that branches.
"""
from app.core.config import settings

if settings.QDRANT_URL:
    from app.rag.vectorstore_qdrant import (  # noqa: F401
        add_chunks,
        delete_document,
        get_all_chunks,
        get_client,
        search,
        search_multi_document,
    )
else:
    from app.rag.vectorstore_chroma import (  # noqa: F401
        add_chunks,
        delete_document,
        get_all_chunks,
        get_client,
        search,
        search_multi_document,
    )
