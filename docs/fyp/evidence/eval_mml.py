"""Evaluation of EchoLearn on "Mathematics for Machine Learning" (Deisenroth, Faisal, Ong).

Run from backend/ with the venv python:  python ../docs/fyp/evidence/eval_mml.py
Reads mml_ingest.json for the document id (uploaded as the local test user) and writes
eval_mml.json next to this file.

Ground truth: for each question, the pages whose extracted text contains the defining
pattern (e.g. "Definition 6.13 (Conjugate Prior)"), excluding front matter (< page 15) and
the index (>= page 400). A citation counts as correct if it is within one page of a
ground-truth page (definitions often start at the foot of one page).
"""
import asyncio
import json
import os
import re
import statistics
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getcwd())

from app.core.database import SessionLocal  # noqa: E402
from app.documents.page_content import load_pages  # noqa: E402
from app.models import Document  # noqa: E402
from app.rag.langgraph_pipeline import run_rag_pipeline  # noqa: E402
from app.rag.retrieval import hybrid_search  # noqa: E402
from app.rag.vectorstore import search as dense_search  # noqa: E402
from app.rag import selection_explainer as se  # noqa: E402

ingest = json.load(open(os.path.join(HERE, "mml_ingest.json")))
DOC_ID = uuid.UUID(ingest["document_id"])

db = SessionLocal()
doc = db.get(Document, DOC_ID)
USER_ID = doc.user_id
pages = load_pages(doc)
page_text = {p["page_number"]: p["text"] for p in pages}

# (question, ground-truth regex, key terms the answer must contain, category)
QUESTIONS = [
    ("Define the rank of a matrix.", r"Basis\s*and\s*Rank|2\.6\.2\s*Rank", ["linearly independent"], "definition"),
    ("What is a positive definite matrix?", r"Symmetric,\s*Positive\s*Definite", ["x"], "definition"),
    ("What is an orthogonal matrix?", r"\(Orthogonal Matrix\)", ["orthonormal", "transpose"], "definition"),
    ("What is an inner product?", r"Inner\s*Products?", ["bilinear", "symmetric"], "definition"),
    ("What is the determinant of a matrix?", r"Determinant\s*and\s*Trace", ["determinant"], "definition"),
    ("What is the eigenvalue equation?", r"Eigenvalues?\s*and\s*Eigenvectors|eigenvalue\s*equation", ["eigen"], "definition"),
    ("What does the singular value decomposition theorem state?", r"Singular\s*Value\s*Decomposition", ["singular", "orthogonal"], "theorem"),
    ("What is the Cholesky decomposition?", r"Cholesky", ["lower", "triangular"], "definition"),
    ("What is the Jacobian?", r"Jacobian", ["partial derivative"], "definition"),
    ("How does backpropagation compute gradients?", r"Backpropagation", ["chain rule"], "concept"),
    ("What is a convex function?", r"Convex\s*Optimization|[Cc]onvex\s*function", ["convex"], "definition"),
    ("What are Lagrange multipliers used for?", r"Lagrange multiplier", ["constrain"], "concept"),
    ("What is a conjugate prior?", r"\(Conjugate Prior\)", ["posterior", "same"], "definition"),
    ("State Bayes' theorem.", r"Bayes.{0,2} (theorem|rule)", ["posterior", "likelihood", "prior"], "theorem"),
    ("What is maximum likelihood estimation?", r"Maximum Likelihood Estimation", ["likelihood"], "concept"),
    ("What is maximum a posteriori (MAP) estimation?", r"Maximum A Posteriori", ["prior"], "concept"),
    ("How does the EM algorithm fit a Gaussian mixture model?", r"EM Algorithm", ["responsibilit"], "algorithm"),
    ("What does PCA maximize when choosing the principal subspace?", r"Maximum\s*Variance", ["variance"], "concept"),
    ("What is the kernel trick in support vector machines?", r"[Kk]ernel\s*trick|[Kk]ernels?\s*\(", ["kernel"], "concept"),
    ("What is the margin in a support vector machine?", r"[Mm]argin(?!al)", ["margin"], "concept"),
    ("What does Example 4.5 compute?", r"Example 4\.5", ["eigen"], "reference"),
    ("What does Definition 6.13 define?", r"Definition 6\.13", ["conjugate"], "reference"),
]
UNANSWERABLE = [
    "Who is the author's favourite football team?",
    "What does the book say about transformers or ChatGPT?",
    "What is the capital of France?",
    "Give me a recipe for chicken biryani.",
    "Who won the 2022 FIFA World Cup?",
    "What is Apple's current stock price?",
    "How do I build a website with the Django framework?",
    "What does the book say about blockchain mining?",
]


def gt_pages(pattern: str) -> list[int]:
    rx = re.compile(pattern)
    return sorted(n for n, t in page_text.items() if 15 <= n < 400 and rx.search(t))


def near(cited: list[int], truth: list[int]) -> bool:
    return any(abs(c - g) <= 1 for c in cited for g in truth)


def page_of(chunk: dict) -> int | None:
    return (chunk.get("metadata") or {}).get("page_number")


def retrieval_eval() -> list[dict]:
    rows = []
    for q, pattern, _, cat in QUESTIONS:
        truth = gt_pages(pattern)
        t = time.perf_counter()
        dense = dense_search(q, USER_ID, [DOC_ID], top_k=8)
        t_dense = time.perf_counter() - t
        t = time.perf_counter()
        hybrid, _ = hybrid_search([q], USER_ID, [DOC_ID], top_k=8)
        t_hybrid = time.perf_counter() - t
        rows.append({
            "question": q, "category": cat, "truth_pages": truth[:12],
            "dense_hit": near([page_of(c) for c in dense if page_of(c)], truth),
            "hybrid_hit": near([page_of(c) for c in hybrid if page_of(c)], truth),
            "dense_ms": round(t_dense * 1000), "hybrid_ms": round(t_hybrid * 1000),
        })
    return rows


async def answer_eval() -> tuple[list[dict], list[dict]]:
    answered, refused = [], []
    for q, pattern, terms, cat in QUESTIONS:
        truth = gt_pages(pattern)
        t = time.perf_counter()
        res = await run_rag_pipeline(question=q, chat_history=[], user_id=USER_ID, document_ids=[DOC_ID])
        secs = time.perf_counter() - t
        cited = [c.get("page_number") for c in res.get("citations", []) if c.get("page_number")]
        text = (res.get("answer") or "").lower()
        answered.append({
            "question": q, "category": cat, "truth_pages": truth[:12], "cited_pages": cited,
            "answered": bool(res.get("was_answered", True)) and "couldn't find" not in text,
            "citation_hit": near(cited, truth),
            "key_terms_present": all(k.lower() in text for k in terms),
            "seconds": round(secs, 1),
            "answer_excerpt": (res.get("answer") or "")[:300],
        })
        await asyncio.sleep(25)  # stay under the answer model's 8,000 tokens-per-minute limit
    for q in UNANSWERABLE:
        t = time.perf_counter()
        res = await run_rag_pipeline(question=q, chat_history=[], user_id=USER_ID, document_ids=[DOC_ID])
        secs = time.perf_counter() - t
        text = (res.get("answer") or "").lower()
        refused.append({
            "question": q,
            "refused": ("couldn't find" in text) or (res.get("was_answered") is False),
            "seconds": round(secs, 1),
            "answer_excerpt": (res.get("answer") or "")[:200],
        })
        await asyncio.sleep(25)
    return answered, refused


def explain_eval() -> list[dict]:
    """Reader 'Explain with AI' on a term, a sentence and a formula line from the book."""
    cases = []
    p_def = gt_pages(r"\(Conjugate Prior\)")[0]
    sentence = next(s for s in re.split(r"(?<=[.])\s+", page_text[p_def].replace("\n", " ")) if "conjugate" in s.lower() and len(s) > 60)
    p_svd = gt_pages(r"Singular\s*Value\s*Decomposition")[0]
    formula = next((ln for ln in page_text[p_svd].split("\n") if "=" in ln and len(ln) < 60), "A = UΣV^T")
    for kind_label, text, page in [("term", "positive definite", gt_pages(r"Symmetric,\s*Positive\s*Definite")[0]),
                                   ("sentence", sentence[:400], p_def), ("formula", formula.strip(), p_svd)]:
        context = se.surrounding_context(page_text[page], text)
        kind = se.classify_selection(text)
        msgs = se.build_messages(text, kind, page, context, [])
        t = time.perf_counter()
        try:
            out = se.explain(msgs, follow_up=False, user_id=USER_ID)
            ok = True
        except se.ExplainError as exc:
            out, ok = {"error": str(exc)}, False
        cases.append({"selection_type": kind_label, "selection": text[:160], "page": page, "classified_as": kind,
                      "ok": ok, "seconds": round(time.perf_counter() - t, 1),
                      "key_points": len(out.get("key_points", [])) if ok else 0,
                      "has_example": bool(out.get("example")) if ok else False,
                      "explanation_excerpt": (out.get("simple_explanation") or "")[:280] if ok else out.get("error")})
    return cases


def provider_counts(since) -> dict:
    from sqlalchemy import func
    from app.models import APICallLog
    rows = (db.query(APICallLog.provider, APICallLog.success, func.count(APICallLog.id))
            .filter(APICallLog.created_at >= since).group_by(APICallLog.provider, APICallLog.success).all())
    return {f"{p} {'ok' if ok else 'failed'}": n for p, ok, n in rows}


def main():
    from datetime import datetime, timezone
    from app.rag.vectorstore import get_all_chunks

    started = datetime.now(timezone.utc)

    chunks = get_all_chunks(DOC_ID)
    print("retrieval…")
    retrieval = retrieval_eval()
    print("answers…")
    answered, refused = asyncio.run(answer_eval())
    print("explain…")
    explain = explain_eval()
    secs = [a["seconds"] for a in answered]
    summary = {
        "document": {"file": "mml-book.pdf", "pages": len(pages), "chunks": len(chunks), "bytes": ingest["bytes"],
                     "processing_seconds": ingest["status_first_seen_at_s"].get("ready"),
                     "indexed_at_seconds": ingest["status_first_seen_at_s"].get("embedded")},
        "retrieval": {"questions": len(retrieval),
                      "dense_hit_at_8": sum(r["dense_hit"] for r in retrieval),
                      "hybrid_hit_at_8": sum(r["hybrid_hit"] for r in retrieval),
                      "dense_median_ms": statistics.median(r["dense_ms"] for r in retrieval),
                      "hybrid_median_ms": statistics.median(r["hybrid_ms"] for r in retrieval)},
        "answers": {"questions": len(answered),
                    "answered": sum(a["answered"] for a in answered),
                    "citation_hit": sum(a["citation_hit"] for a in answered),
                    "key_terms_present": sum(a["key_terms_present"] for a in answered),
                    "median_seconds": statistics.median(secs), "max_seconds": max(secs)},
        "refusals": {"questions": len(refused), "correctly_refused": sum(r["refused"] for r in refused)},
        "explain": {"cases": len(explain), "ok": sum(e["ok"] for e in explain)},
    }
    summary["llm_calls_by_provider"] = provider_counts(started)
    out = {"summary": summary, "retrieval": retrieval, "answers": answered, "refusals": refused, "explain": explain}
    json.dump(out, open(os.path.join(HERE, "eval_mml.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
