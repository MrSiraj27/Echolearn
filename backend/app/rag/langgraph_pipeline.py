import json
import logging
import re
import uuid
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.admin.api_logging import log_api_call
from app.rag.llm import chat_completion, get_groq_client
from app.rag.prompts import (
    FOLLOW_UP_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    QUERY_REWRITE_PROMPT,
    RELEVANCE_GRADE_PROMPT,
)
from app.rag.smalltalk import detect_smalltalk_reply
from app.rag.vectorstore import search, search_multi_document

logger = logging.getLogger(__name__)

REWRITE_MODEL = "openai/gpt-oss-20b"
ANSWER_MODEL = "openai/gpt-oss-120b"
RETRIEVAL_TOP_K = 8
RELEVANCE_DISTANCE_THRESHOLD = 1.1  # chroma cosine distance; lower = more similar


class RagState(TypedDict, total=False):
    question: str
    chat_history: list[dict]
    user_id: str
    document_ids: list[str]
    rewritten_query: str
    retrieved_chunks: list[dict]
    has_relevant_context: bool
    answer: str
    citations: list[dict]


def _format_history(chat_history: list[dict]) -> str:
    if not chat_history:
        return "(no prior conversation)"
    lines = [f"{m['role']}: {m['content']}" for m in chat_history]
    return "\n".join(lines)


def rewrite_query_node(state: RagState) -> RagState:
    if not state.get("chat_history"):
        return {"rewritten_query": state["question"]}

    prompt = QUERY_REWRITE_PROMPT.format(
        chat_history=_format_history(state["chat_history"]), question=state["question"]
    )
    try:
        rewritten = chat_completion(
            [{"role": "user", "content": prompt}], model=REWRITE_MODEL, temperature=0.0
        ).strip()
        return {"rewritten_query": rewritten or state["question"]}
    except Exception:
        logger.exception("Query rewrite failed, falling back to original question")
        return {"rewritten_query": state["question"]}


def retrieve_node(state: RagState) -> RagState:
    document_ids = [uuid.UUID(d) for d in state["document_ids"]]
    # Meta-queries ("summarize this") need broad coverage of the document rather than
    # chunks narrowly similar to the literal instruction text, so pull more of them.
    top_k = RETRIEVAL_TOP_K * 2 if _is_meta_query(state["question"]) else RETRIEVAL_TOP_K
    user_id = uuid.UUID(state["user_id"])

    if len(document_ids) > 1:
        # Multiple documents in play (a folder or workspace chat) — use two-stage
        # per-document retrieval so a large/dominant document can't crowd smaller ones
        # out of the final context.
        chunks = search_multi_document(state["rewritten_query"], user_id, document_ids, top_k=top_k, per_doc_k=3)
    else:
        chunks = search(state["rewritten_query"], user_id, document_ids, top_k=top_k)
    return {"retrieved_chunks": chunks}


_META_QUERY_PATTERN = re.compile(
    r"\b(summarize|summary|summarise|overview|main points?|key points?|"
    r"what is this (document|file|doc) about|tl;?dr|tell me about this)\b",
    re.IGNORECASE,
)


def _is_meta_query(question: str) -> bool:
    """Instructions like 'summarize this' don't share vocabulary with the content they're
    asking about, so semantic similarity search naturally scores them as dissimilar even
    when the retrieved chunks are exactly what should be summarized. Treat any retrieval
    as relevant for these — if the user's own document produced chunks at all, there's
    something to summarize."""
    return bool(_META_QUERY_PATTERN.search(question))


def grade_relevance_node(state: RagState) -> RagState:
    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        return {"has_relevant_context": False}

    if _is_meta_query(state["question"]):
        return {"has_relevant_context": True}

    # Fast path: if the closest chunk is well within the similarity threshold, skip the LLM call.
    best_distance = min(c["distance"] for c in chunks)
    if best_distance <= RELEVANCE_DISTANCE_THRESHOLD * 0.6:
        return {"has_relevant_context": True}

    excerpts = "\n\n".join(c["text"][:500] for c in chunks[:4])
    prompt = RELEVANCE_GRADE_PROMPT.format(question=state["question"], excerpts=excerpts)
    try:
        verdict = chat_completion(
            [{"role": "user", "content": prompt}], model=REWRITE_MODEL, temperature=0.0
        ).strip().lower()
        return {"has_relevant_context": verdict.startswith("yes")}
    except Exception:
        logger.exception("Relevance grading failed, defaulting to distance threshold")
        return {"has_relevant_context": best_distance <= RELEVANCE_DISTANCE_THRESHOLD}


def _route_after_grading(state: RagState) -> str:
    return "generate_answer" if state.get("has_relevant_context") else "not_found"


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _source_label(metadata: dict) -> str:
    filename = metadata.get("filename")
    start_time = metadata.get("start_time_seconds")
    if start_time is not None:
        return f"[Source: {filename}, at {_format_timestamp(start_time)}]"
    return f"[Source: {filename}, page {metadata.get('page_number')}]"


def build_answer_messages(state: RagState) -> list[dict]:
    chunks = state.get("retrieved_chunks") or []
    context = "\n\n".join(f"{_source_label(c['metadata'])}\n{c['text']}" for c in chunks)

    system_prompt = GROUNDING_SYSTEM_PROMPT.format(context=context)
    messages = [{"role": "system", "content": system_prompt}]

    for turn in state.get("chat_history", [])[-3:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": state["question"]})
    return messages


def build_citations(state: RagState) -> list[dict]:
    chunks = state.get("retrieved_chunks") or []
    citations = [
        {
            "filename": c["metadata"].get("filename"),
            "page_number": c["metadata"].get("page_number"),
            "document_id": c["metadata"].get("document_id"),
            "chunk_text": c["text"],
            "start_time_seconds": c["metadata"].get("start_time_seconds"),
        }
        for c in chunks
    ]
    seen = set()
    unique_citations = []
    for c in citations:
        key = (c["filename"], c["page_number"], c["start_time_seconds"])
        if key not in seen:
            seen.add(key)
            unique_citations.append(c)
    return unique_citations


def generate_follow_ups(question: str, answer: str, chunks: list[dict]) -> list[str]:
    if not chunks:
        return []

    context = "\n\n".join(c["text"][:400] for c in chunks[:4])
    prompt = FOLLOW_UP_PROMPT.format(context=context, question=question, answer=answer)

    try:
        raw = chat_completion([{"role": "user", "content": prompt}], model=REWRITE_MODEL, temperature=0.4)
        # Models sometimes wrap JSON in a code fence — strip it before parsing.
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        suggestions = json.loads(cleaned)
        if isinstance(suggestions, list):
            return [str(s).strip() for s in suggestions if str(s).strip()][:2]
    except Exception:
        logger.warning("Follow-up suggestion generation failed", exc_info=True)

    return []


def generate_answer_node(state: RagState) -> RagState:
    messages = build_answer_messages(state)

    try:
        answer = chat_completion(messages, model=ANSWER_MODEL, temperature=0.2, purpose="chat_answer")
    except Exception:
        logger.exception("Answer generation failed")
        answer = "Sorry, I ran into an error generating a response. Please try again."

    return {"answer": answer, "citations": build_citations(state)}


def not_found_node(state: RagState) -> RagState:
    return {
        "answer": (
            "I couldn't find this in your document(s). Try rephrasing your question, "
            "or double-check that the right document is selected for this chat."
        ),
        "citations": [],
    }


def build_graph():
    graph = StateGraph(RagState)

    graph.add_node("rewrite_query", rewrite_query_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade_relevance", grade_relevance_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("not_found", not_found_node)

    graph.set_entry_point("rewrite_query")
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("retrieve", "grade_relevance")
    graph.add_conditional_edges(
        "grade_relevance", _route_after_grading, {"generate_answer": "generate_answer", "not_found": "not_found"}
    )
    graph.add_edge("generate_answer", END)
    graph.add_edge("not_found", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_rag_pipeline(
    question: str,
    chat_history: list[dict],
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> dict:
    smalltalk_reply = detect_smalltalk_reply(question)
    if smalltalk_reply is not None:
        return {"answer": smalltalk_reply, "citations": [], "follow_ups": [], "was_answered": True}

    graph = get_graph()
    result = graph.invoke(
        {
            "question": question,
            "chat_history": chat_history,
            "user_id": str(user_id),
            "document_ids": [str(d) for d in document_ids],
        }
    )
    answer = result.get("answer", "")
    has_context = bool(result.get("has_relevant_context"))
    follow_ups = generate_follow_ups(question, answer, result.get("retrieved_chunks") or []) if has_context else []
    return {
        "answer": answer,
        "citations": result.get("citations", []),
        "follow_ups": follow_ups,
        "was_answered": has_context,
    }


async def stream_rag_pipeline(
    question: str,
    chat_history: list[dict],
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
):
    """Run retrieval + grading, then yield answer tokens as they stream from the LLM.

    Yields (event_type, payload) tuples: ("token", str) for each chunk of the answer,
    then ("done", {"citations": [...]}) once complete.
    """
    smalltalk_reply = detect_smalltalk_reply(question)
    if smalltalk_reply is not None:
        yield ("token", smalltalk_reply)
        yield ("done", {"citations": [], "follow_ups": [], "was_answered": True})
        return

    state: RagState = {
        "question": question,
        "chat_history": chat_history,
        "user_id": str(user_id),
        "document_ids": [str(d) for d in document_ids],
    }

    state.update(rewrite_query_node(state))
    state.update(retrieve_node(state))
    state.update(grade_relevance_node(state))

    if not state.get("has_relevant_context"):
        result = not_found_node(state)
        yield ("token", result["answer"])
        yield ("done", {"citations": result["citations"], "follow_ups": [], "was_answered": False})
        return

    messages = build_answer_messages(state)
    citations = build_citations(state)
    full_answer = ""

    try:
        with log_api_call("groq", "chat_answer_stream"):
            client = get_groq_client()
            stream = client.chat.completions.create(
                model=ANSWER_MODEL, messages=messages, temperature=0.2, stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_answer += delta
                    yield ("token", delta)
    except Exception:
        logger.warning("Streaming Groq call failed, falling back to non-streaming completion", exc_info=True)
        try:
            full_answer = chat_completion(messages, model=ANSWER_MODEL, temperature=0.2, purpose="chat_answer")
        except Exception:
            logger.exception("Fallback answer generation also failed")
            full_answer = "Sorry, I ran into an error generating a response. Please try again."
        yield ("token", full_answer)

    follow_ups = generate_follow_ups(question, full_answer, state.get("retrieved_chunks") or [])
    yield ("done", {"citations": citations, "follow_ups": follow_ups, "was_answered": True})
