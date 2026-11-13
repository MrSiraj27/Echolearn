"""Retrieval evaluation on the Sahih Muslim collection (7 PDFs, indexed in the app).
System A = dense-only multi-document search (what the chat used before).
System B = hybrid search (dense + BM25 + reference lookup + continuation)."""
import sys, re, json, random, time, uuid, statistics
sys.path.insert(0, ".")
from app.rag.vectorstore import get_client, search_multi_document, get_all_chunks
from app.rag.retrieval import hybrid_search, tokenize

ids = ["5adfc286-c872-4d20-99dd-90300356046b","b5dab6c5-fc78-4e07-b30d-291ac66ffdd2","18291287-1034-4f6c-b1c6-4ffdef7be516","a935329e-4eda-4796-b9f0-0c900dc7bbd1","58dfb797-4323-4366-a1eb-ebe195afac1b","97947449-a049-4150-9794-cc31563d356a","cf87a312-5299-4090-9f15-ff1c46bc2434"]
docs = [uuid.UUID(i) for i in ids]
col = get_client().get_collection("echolearn_docs")
uid = uuid.UUID(col.get(where={"document_id": ids[0]}, limit=1, include=["metadatas"])["metadatas"][0]["user_id"])
chunks = get_all_chunks(docs[0], docs)
print("corpus chunks:", len(chunks))
K = 8
rng = random.Random(2026)

# ---- Task 1: numbered reference queries. Ground truth = the chunk holding the "[N]" marker, N unique in corpus.
marker = re.compile(r"(?:^|\n)\s*\[(\d{1,4})\]")
holders = {}
for c in chunks:
    for m in marker.finditer(c["text"]):
        holders.setdefault(m.group(1), []).append(c["text"])
unique = [n for n, v in holders.items() if len(v) == 1 and 1 <= int(n) <= 7500]
print("numbered items with a unique marker:", len(unique))
sample1 = rng.sample(sorted(unique, key=int), 60)
templates = ["tell me about {n} hadees", "what does hadith number {n} say"]

# ---- Task 2: exact-phrase queries (5 consecutive content words from a random chunk)
def phrase(text):
    words = [w for w in re.findall(r"[A-Za-z']+", text) if len(w) > 3]
    if len(words) < 12: return None
    i = rng.randrange(2, len(words) - 7)
    return " ".join(words[i:i+5])
pool = [c for c in chunks if len(c["text"]) > 400]
rng.shuffle(pool)
sample2 = []
for c in pool:
    p = phrase(c["text"])
    if p: sample2.append((p, c["text"]))
    if len(sample2) == 60: break

def run(system, q):
    t = time.perf_counter()
    if system == "A":
        res = search_multi_document(q, uid, docs, top_k=K, per_doc_k=3)
    else:
        res, _ = hybrid_search([q], uid, docs, top_k=K, per_doc_k=3)
        res = res[:K] if False else res  # keep pinned continuation chunks, as the app does
    return res, (time.perf_counter() - t) * 1000

# warm up index + embedding model so latency excludes one-off loading
t0 = time.perf_counter(); run("B", "warm up query"); print(f"first hybrid call (builds index): {time.perf_counter()-t0:.2f}s")
run("A", "warm up query")

def evaluate(items, system, label, phrases=None):
    hits, lat, ranks, lenient = 0, [], [], 0
    for qi, (q, truth) in enumerate(items):
        res, ms = run(system, q)
        lat.append(ms)
        texts = [r["text"] for r in res]
        if truth in texts:
            hits += 1
            ranks.append(texts.index(truth) + 1)
        if phrases:
            want = set(re.findall(r"[a-z']+", phrases[qi].lower()))
            if any(want <= set(re.findall(r"[a-z']+", t.lower())) for t in texts):
                lenient += 1
    n = len(items)
    out = {"lenient_hits": lenient, "n": n, "hits": hits, "recall": round(hits / n, 3),
           "mean_rank_when_found": round(statistics.mean(ranks), 2) if ranks else None,
           "median_latency_ms": round(statistics.median(lat)), "p95_latency_ms": round(sorted(lat)[int(0.95 * (n - 1))])}
    print(f"{label:34s} system {system}: recall@{K} {hits}/{n} = {out['recall']:.0%}  mean rank {out['mean_rank_when_found']}  median {out['median_latency_ms']} ms")
    return out

results = {}
for ti, tpl in enumerate(templates):
    items = [(tpl.format(n=n), holders[n][0]) for n in sample1]
    for s in "AB":
        results[f"ref_t{ti+1}_{s}"] = evaluate(items, s, f"reference query: '{tpl}'")
items = [(f"what does it say about {p}", truth) for p, truth in sample2]
for s in "AB":
    results[f"phrase_{s}"] = evaluate(items, s, "exact-phrase query", phrases=[p for p, _ in sample2])
    print("   lenient (phrase in any returned chunk):", results[f"phrase_{s}"]["lenient_hits"], "/", len(items))
json.dump({"corpus_chunks": len(chunks), "unique_numbered": len(unique), "results": results}, open(sys.argv[1] + "/eval_results.json", "w"), indent=1)
