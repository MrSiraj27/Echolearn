"""One-off recovery script: re-runs the parse+chunk+embed pipeline for every
document currently marked ready/embedded, used after the Chroma persistent
index was found corrupted and reset to an empty collection. Not part of the
normal app — safe to delete after use."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.documents.background import run_parsing_task
from app.models import Document, DocumentStatus

db = SessionLocal()
docs = db.query(Document).filter(Document.status.in_([DocumentStatus.ready, DocumentStatus.embedded])).all()
print(f"Re-embedding {len(docs)} documents...")

for i, doc in enumerate(docs, 1):
    print(f"[{i}/{len(docs)}] {doc.filename} ({doc.id})")
    ext = doc.file_type
    try:
        run_parsing_task(doc.id, doc.storage_path, ext)
    except Exception as exc:
        print(f"  FAILED: {exc}")

db.close()
print("Done.")
