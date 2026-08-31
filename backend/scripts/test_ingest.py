"""Manual end-to-end test: parse -> chunk -> embed -> search, for a sample text.

Run from backend/: venv/Scripts/python.exe scripts/test_ingest.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.chunking import chunk_text
from app.rag.vectorstore import add_chunks, search

SAMPLE_TEXT = """
EchoLearn is a document-only RAG chat platform. It lets users upload PDFs, Word
documents, PowerPoint slides, spreadsheets, and images, then ask questions that are
answered strictly from the content of those documents.

The system uses a LangGraph pipeline: the user's question is rewritten for better
retrieval, relevant chunks are retrieved from a vector store, a relevance check runs,
and only then is an answer generated using Groq's Llama models. If nothing relevant is
found, EchoLearn tells the user it could not find the answer in their documents rather
than guessing from general knowledge.

Elephants are the largest land animals on Earth and live in matriarchal herds.
"""

QUERY = "What does EchoLearn do when it can't find an answer in the documents?"


def main():
    document_id = uuid.uuid4()
    user_id = uuid.uuid4()

    pages = [{"page_number": 1, "text": SAMPLE_TEXT}]
    chunks = chunk_text(pages, document_id, user_id, "sample.txt")
    print(f"Generated {len(chunks)} chunks.")

    add_chunks(document_id, user_id, chunks)
    print("Chunks embedded and stored.")

    results = search(QUERY, user_id, [document_id], top_k=3)
    print(f"\nQuery: {QUERY}\n")
    for i, r in enumerate(results, start=1):
        print(f"--- Result {i} (distance={r['distance']:.4f}) ---")
        print(r["text"].strip())
        print()


if __name__ == "__main__":
    main()
