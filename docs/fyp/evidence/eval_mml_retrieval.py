"""Retrieval evaluation on "Mathematics for Machine Learning" (417 pages), dense-only vs hybrid.

No language model is called, so the numbers measure retrieval alone and are not affected by
provider quotas. Run from backend/:  python ../docs/fyp/evidence/eval_mml_retrieval.py
Writes eval_mml_retrieval.json next to this file.

Query sets (fixed seed 2026):
  1. Concept questions: the 22 questions of eval_mml.py; hit = a returned chunk within one page of
     a page whose text holds the defining heading.
  2. Numbered labels: 60 labels such as "Example 4.5", "Definition 6.13", "Theorem 4.3" sampled from
     those that appear in the book, asked as "What does {label} say?"; hit = a returned chunk that
     contains the label (ignoring the spaces the PDF extractor drops).
  3. Exact phrases: five consecutive words (longer than three letters) from 60 random chunks, asked as
     "what does it say about ..."; strict hit = the same chunk returned, lenient hit = all five words
     in some returned chunk.
"""
import json
import os
import random
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
from app.rag.retrieval import hybrid_search  # noqa: E402
from app.rag.vectorstore import get_all_chunks, search as dense_search  # noqa: E402

sys.path.insert(0, HERE)
from eval_mml import QUESTIONS  # noqa: E402  (loads the same document; no model calls at import)

K = 8
rng = random.Random(2026)
DOC_ID = uuid.UUID(json.load(open(os.path.join(HERE, "mml_ingest.json")))["document_id"])
db = SessionLocal()
doc = db.get(Document, DOC_ID)
USER_ID = doc.user_id
page_text = {p["page_number"]: p["text"] for p in load_pages(doc)}
chunks = get_all_chunks(DOC_ID)
print("pages", len(page_text), "chunks", len(chunks))


def squash(t: str) -> str:
    return re.sub(r"\s+", "", t).lower()


def page_of(c):
    return (c.get("metadata") or {}).get("page_number")


def run(system, q):
    t = time.perf_counter()
    if system == "dense":
        res = dense_search(q, USER_ID, [DOC_ID], top_k=K)
    else:
        res, _ = hybrid_search([q], USER_ID, [DOC_ID], top_k=K)
    return res, (time.perf_counter() - t) * 1000


t0 = time.perf_counter()
run("hybrid", "warm up")
first_call_s = round(time.perf_counter() - t0, 2)
run("dense", "warm up")

# ---- 1. concept questions
concept = []
for q, pattern, _, cat in QUESTIONS:
    if cat == "reference":
        continue  # numbered references are measured in set 2
    rx = re.compile(pattern)
    truth = [n for n, t in page_text.items() if 15 <= n < 400 and rx.search(t)]
    concept.append((q, truth))

# ---- 2. numbered labels
label_rx = re.compile(r"(Example|Definition|Theorem)\s*(\d{1,2}\.\d{1,2})")
labels = sorted({f"{m.group(1)} {m.group(2)}" for n, t in page_text.items() if 15 <= n < 400
                 for m in label_rx.finditer(t)})
sample_labels = rng.sample(labels, min(60, len(labels)))

# ---- 3. exact phrases
def phrase(text):
    words = [w for w in re.findall(r"[A-Za-z']+", text) if len(w) > 3]
    if len(words) < 12:
        return None
    i = rng.randrange(2, len(words) - 7)
    return " ".join(words[i:i + 5])


pool = [c for c in chunks if len(c["text"]) > 400 and 15 <= (page_of(c) or 0) < 400]
rng.shuffle(pool)
phrases = []
for c in pool:
    p = phrase(c["text"])
    if p:
        phrases.append((p, c["text"]))
    if len(phrases) == 60:
        break


def evaluate(system):
    out = {}
    hits, lat = 0, []
    for q, truth in concept:
        res, ms = run(system, q)
        lat.append(ms)
        hits += any(abs((page_of(c) or -9) - g) <= 1 for c in res for g in truth)
    out["concept"] = {"n": len(concept), "hits": hits, "median_ms": round(statistics.median(lat))}

    hits, ranks, lat = 0, [], []
    for label in sample_labels:
        res, ms = run(system, f"What does {label} say?")
        lat.append(ms)
        key = squash(label)
        found = [i for i, c in enumerate(res) if key in squash(c["text"])]
        if found:
            hits += 1
            ranks.append(found[0] + 1)
    out["labels"] = {"n": len(sample_labels), "hits": hits, "median_ms": round(statistics.median(lat)),
                     "mean_rank": round(statistics.mean(ranks), 2) if ranks else None}

    strict, lenient, ranks, lat = 0, 0, [], []
    for p, truth in phrases:
        res, ms = run(system, f"what does it say about {p}")
        lat.append(ms)
        texts = [c["text"] for c in res]
        if truth in texts:
            strict += 1
            ranks.append(texts.index(truth) + 1)
        want = set(re.findall(r"[a-z']+", p.lower()))
        if any(want <= set(re.findall(r"[a-z']+", t.lower())) for t in texts):
            lenient += 1
    out["phrases"] = {"n": len(phrases), "strict": strict, "lenient": lenient,
                      "mean_rank": round(statistics.mean(ranks), 2) if ranks else None,
                      "median_ms": round(statistics.median(lat))}
    return out


results = {"dense": evaluate("dense"), "hybrid": evaluate("hybrid")}
summary = {"pages": len(page_text), "chunks": len(chunks), "labels_in_book": len(labels),
           "first_hybrid_call_s": first_call_s, "results": results,
           "sample_labels": sample_labels, "sample_phrases": [p for p, _ in phrases]}
json.dump(summary, open(os.path.join(HERE, "eval_mml_retrieval.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if not k.startswith("sample")}, indent=1))
