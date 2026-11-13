"""Hybrid retrieval: dense (semantic) search + keyword (BM25) search + reference lookup.

Why this exists: the dense embedding model (MiniLM) captures meaning but is nearly blind to
numbers, identifiers and exact wording. "tell me about hadith 240" or "what is on page 12"
then retrieves chunks that merely *sound* related and misses the one that literally contains
"[240]". Real study material is full of such references (hadith/verse/section/article numbers,
question numbers, page numbers), so retrieval combines three signals:

  1. reference lookup - a number the user cites ("hadith 240", "no. 12", "#7") is matched
     against bracketed/numbered markers in the text ("[240] ...", "240 - (153)") and
     the matching chunk is pinned to the top, together with the text that continues onto
     the next page;
  2. BM25 keyword search over every chunk of the chat's documents;
  3. dense search (the existing vector store), for several phrasings of the question.

The three ranked lists are merged with reciprocal rank fusion. Nothing here needs re-indexing:
the keyword index is built in memory from the chunks already stored in the vector store.
"""
import heapq
import logging
import math
import re
import threading
import time
import uuid
from collections import OrderedDict, defaultdict

from app.rag.chunking import clean_text  # noqa: F401  (re-exported for the pipeline)
from app.rag.vectorstore import get_all_chunks, search, search_multi_document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------
# query understanding (cheap, deterministic)
# ---------------------------------------------------------------------------------------------

# Spelling variants users type (Roman Urdu / transliteration) -> the word the books use.
_ALIASES = {
    "hadees": "hadith", "hadis": "hadith", "hadeeth": "hadith", "hadeth": "hadith",
    "hadits": "hadith", "ahadees": "hadith", "ahadis": "hadith", "ahadeeth": "hadith",
    "ahadith": "hadith", "hadiths": "hadith", "hadithen": "hadith",
    "namaz": "prayer salat", "roza": "fasting sawm", "zakat": "zakah", "wudu": "wudu ablution",
    "wazu": "wudu ablution", "hajj": "hajj pilgrimage",
}

# A number is treated as a *reference* ("item no. 240") only if one of these words is present;
# otherwise ("top 5 reasons", "in 2019") it is just another keyword.
_REFERENCE_WORDS = {
    "hadith", "hadees", "hadis", "hadeeth", "ahadith", "number", "no", "num", "numbered",
    "verse", "ayah", "ayat", "section", "chapter", "article", "clause", "rule", "item",
    "question", "q", "exercise", "problem", "figure", "table", "example", "paragraph", "para",
}

_PAGE_PATTERN = re.compile(r"\b(?:page|pages|pg|p)\.?\s*#?\s*(\d{1,4})\b", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"(?<![\w.])\d{1,6}(?![\w.]*\d)")

_STOPWORDS = frozenset(
    "a an the and or but if of to in on at by for with from as is are was were be been being "
    "it its this that these those i me my we our you your he she they them his her their "
    "what which who whom whose when where why how do does did doing have has had having "
    "can could should would will shall may might must not no nor so than too very just "
    "about into over under again further then once here there all any both each few more "
    "most other some such only own same tell me give show explain please".split()
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\w+", clean_text(text).lower())
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


def normalize_query(query: str) -> str:
    """Rewrite known spelling variants to the form the documents use (hadees -> hadith)."""

    def _sub(match: re.Match) -> str:
        return _ALIASES.get(match.group(0).lower(), match.group(0))

    return re.sub(r"[A-Za-z]+", _sub, query)


def extract_reference_numbers(query: str) -> list[str]:
    """Numbers the user is citing as an item reference, in order of appearance."""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", query)}
    has_reference_word = bool(words & _REFERENCE_WORDS) or "#" in query or "[" in query
    if not has_reference_word:
        return []
    page_numbers = {m.group(1) for m in _PAGE_PATTERN.finditer(query)}
    seen: list[str] = []
    for m in _NUMBER_PATTERN.finditer(query):
        n = m.group(0).lstrip("0") or "0"
        if m.group(0) not in page_numbers and n not in seen:
            seen.append(n)
    return seen[:3]


def extract_page_numbers(query: str) -> list[int]:
    return [int(m.group(1)) for m in _PAGE_PATTERN.finditer(query)][:2]


# ---------------------------------------------------------------------------------------------
# in-memory keyword index (BM25) per set of documents
# ---------------------------------------------------------------------------------------------

_MAX_CHUNKS_PER_INDEX = 25_000  # beyond this, skip keyword search rather than risk memory
_MAX_CACHED_INDEXES = 3
_INDEX_TTL_SECONDS = 300
_BM25_K1 = 1.4
_BM25_B = 0.75


class _Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths: list[int] = []
        self.by_page: dict[tuple[str, int], list[int]] = defaultdict(list)
        for i, chunk in enumerate(chunks):
            tokens = tokenize(chunk["text"])
            self.lengths.append(len(tokens))
            counts: dict[str, int] = defaultdict(int)
            for t in tokens:
                counts[t] += 1
            for term, tf in counts.items():
                self.postings[term].append((i, tf))
            page = chunk["metadata"].get("page_number")
            if page is not None:
                self.by_page[(str(chunk["metadata"].get("document_id")), int(page))].append(i)
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        self.built_at = time.monotonic()

    def bm25(self, query_tokens: list[str], limit: int, number_boost: float = 2.0) -> list[tuple[int, float]]:
        n = len(self.chunks)
        scores: dict[int, float] = defaultdict(float)
        for term in set(query_tokens):
            plist = self.postings.get(term)
            if not plist:
                continue
            df = len(plist)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            weight = number_boost if term.isdigit() else 1.0
            for i, tf in plist:
                denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * self.lengths[i] / self.avg_length)
                scores[i] += weight * idf * (tf * (_BM25_K1 + 1)) / denom
        return heapq.nlargest(limit, scores.items(), key=lambda kv: kv[1])


_index_cache: "OrderedDict[tuple, _Index]" = OrderedDict()
_index_lock = threading.Lock()


def _get_index(user_id: uuid.UUID, document_ids: list[uuid.UUID]) -> _Index | None:
    key = (str(user_id), frozenset(str(d) for d in document_ids))
    now = time.monotonic()
    with _index_lock:
        cached = _index_cache.get(key)
        if cached and now - cached.built_at < _INDEX_TTL_SECONDS:
            _index_cache.move_to_end(key)
            return cached

    chunks = get_all_chunks(document_ids[0], document_ids)
    uid = str(user_id)
    chunks = [c for c in chunks if str(c["metadata"].get("user_id", uid)) == uid]
    if not chunks or len(chunks) > _MAX_CHUNKS_PER_INDEX:
        if chunks:
            logger.warning("Keyword index skipped: %d chunks exceeds %d", len(chunks), _MAX_CHUNKS_PER_INDEX)
        return None

    started = time.monotonic()
    index = _Index(chunks)
    logger.info("Built keyword index: %d chunks in %.2fs", len(chunks), time.monotonic() - started)
    with _index_lock:
        _index_cache[key] = index
        _index_cache.move_to_end(key)
        while len(_index_cache) > _MAX_CACHED_INDEXES:
            _index_cache.popitem(last=False)
    return index


# ---------------------------------------------------------------------------------------------
# reference lookup
# ---------------------------------------------------------------------------------------------


def _primary_marker(number: str) -> re.Pattern:
    # "[240] 131 - (78) It was narrated..." - the bracketed number that starts a numbered item
    return re.compile(rf"\[\s*{re.escape(number)}\s*\]")


def _secondary_marker(number: str) -> re.Pattern:
    # other numbering systems printed alongside: "[386] 240 - (153)" or "25 - (240)"
    n = re.escape(number)
    return re.compile(rf"(?<![\[\d]){n}\s*[-–:]\s*\(\d+\)|\({n}\)")


def _find_references(index: _Index, numbers: list[str]) -> tuple[list[int], list[int]]:
    primary: list[int] = []
    secondary: list[int] = []
    for number in numbers:
        p, s = _primary_marker(number), _secondary_marker(number)
        for i, chunk in enumerate(index.chunks):
            text = chunk["text"]
            if p.search(text):
                primary.append(i)
            elif s.search(text):
                secondary.append(i)
    return primary, secondary


def _continuation(index: _Index, i: int, limit: int = 4) -> list[int]:
    """Chunks that continue the passage in chunk `i`. Chunks of one page overlap (the splitter
    repeats ~150 chars), so the successor is the chunk whose opening appears in this chunk's
    tail. When the chunk is the last on its page the passage runs onto the next page - a
    numbered item routinely does - so that page's chunks follow. Without this the model gets
    half a passage."""
    meta = index.chunks[i]["metadata"]
    page = meta.get("page_number")
    if page is None:
        return []
    doc = str(meta.get("document_id"))
    same_page = index.by_page.get((doc, int(page)), [])

    out: list[int] = []
    cur = i
    reached_page_end = False
    for _ in range(3):
        tail = index.chunks[cur]["text"][-200:]
        successor = None
        for j in same_page:
            if j == i or j in out or j == cur:
                continue
            head = index.chunks[j]["text"][:40]
            if len(head) >= 20 and head in tail:
                successor = j
                break
        if successor is None:
            reached_page_end = True
            break
        out.append(successor)
        cur = successor

    if reached_page_end:
        out.extend(index.by_page.get((doc, int(page) + 1), [])[:3])
    return out[:limit]


# ---------------------------------------------------------------------------------------------
# fusion
# ---------------------------------------------------------------------------------------------


def _key(chunk: dict) -> tuple:
    m = chunk["metadata"]
    return (m.get("document_id"), m.get("page_number"), m.get("start_time_seconds"), chunk["text"][:80])


def _dense(question: str, user_id, document_ids, top_k: int, per_doc_k: int) -> list[dict]:
    if len(document_ids) > 1:
        return search_multi_document(question, user_id, document_ids, top_k=top_k, per_doc_k=per_doc_k)
    return search(question, user_id, document_ids, top_k=top_k)


def hybrid_search(
    queries: list[str],
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    top_k: int = 8,
    per_doc_k: int = 3,
) -> tuple[list[dict], dict]:
    """Return (chunks, info). `queries` are phrasings of the same question (the user's own
    wording first). `info` reports how the result was found, for grading/logging."""
    if not document_ids or not queries:
        return [], {}

    normalized = [normalize_query(q) for q in queries]
    # Numbers/pages can survive only in the rewritten form of a follow-up question, so read
    # them from every phrasing, not just the first.
    numbers: list[str] = []
    pages: list[int] = []
    for q in queries:
        numbers += [n for n in extract_reference_numbers(q) if n not in numbers]
        pages += [p for p in extract_page_numbers(q) if p not in pages]
    numbers, pages = numbers[:3], pages[:2]

    index = None
    try:
        index = _get_index(user_id, document_ids)
    except Exception:
        logger.warning("Keyword index unavailable, falling back to dense search only", exc_info=True)

    ranked: list[list[dict]] = []
    for q in dict.fromkeys(normalized):  # de-dupe, keep order
        try:
            ranked.append(_dense(q, user_id, document_ids, top_k, per_doc_k))
        except Exception:
            logger.warning("Dense search failed for query %r", q, exc_info=True)

    pinned: list[tuple[dict, str]] = []
    info = {"reference_numbers": numbers, "reference_hits": 0, "page_hits": 0, "keyword_hits": 0}

    if index is not None:
        # 1. reference lookup: the item itself, immediately followed by its continuation
        #    (so the model reads it as one passage), then the same number in other numbering
        #    systems. Tags let the answer prompt tell them apart.
        if numbers:
            primary, secondary = _find_references(index, numbers)
            info["reference_hits"] = len(primary)
            for rank, i in enumerate(primary[:4]):
                pinned.append((index.chunks[i], "reference"))
                if rank < 2:
                    for j in _continuation(index, i):
                        pinned.append((index.chunks[j], "continuation"))
            for i in secondary[:2]:
                pinned.append((index.chunks[i], "alt_numbering"))

        # 2. explicit page request
        for page in pages:
            for doc in document_ids[:8]:
                for i in index.by_page.get((str(doc), page), [])[:3]:
                    pinned.append((index.chunks[i], "page"))
                    info["page_hits"] += 1

        # 3. keyword search
        q_tokens: list[str] = []
        for q in normalized:
            q_tokens.extend(tokenize(q))
        keyword = [index.chunks[i] for i, _ in index.bm25(q_tokens, limit=max(top_k * 2, 12))]
        info["keyword_hits"] = len(keyword)
        ranked.append(keyword)

    # reciprocal rank fusion of dense lists + keyword list
    scores: dict[tuple, float] = defaultdict(float)
    by_key: dict[tuple, dict] = {}
    for lst in ranked:
        for rank, chunk in enumerate(lst):
            k = _key(chunk)
            scores[k] += 1.0 / (60 + rank)
            by_key.setdefault(k, chunk)
    fused = [by_key[k] for k, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]

    merged: list[dict] = []
    seen: set[tuple] = set()
    for chunk, tag in [(c, t) for c, t in pinned] + [(c, None) for c in fused]:
        k = _key(chunk)
        if k in seen:
            continue
        seen.add(k)
        item = dict(chunk)
        # keyword-only hits have no vector distance; keep them out of the "very close
        # semantic match" fast path in grading.
        item.setdefault("distance", 0.9)
        if tag:
            item["match"] = tag
        merged.append(item)

    # pinned items are always kept; the remaining budget goes to the fused ranking
    budget = max(top_k, len(pinned)) + (4 if pinned else 0)
    return merged[:budget], info
