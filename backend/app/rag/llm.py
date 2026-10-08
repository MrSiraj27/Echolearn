import logging

from groq import Groq
import google.generativeai as genai

from app.admin.api_logging import log_api_call
from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY, timeout=45.0, max_retries=1)
    return _groq_client


def _groq_chat(model: str, messages: list[dict], temperature: float = 0.2, extra: dict | None = None) -> str:
    client = get_groq_client()
    response = client.chat.completions.create(model=model, messages=messages, temperature=temperature, **(extra or {}))
    return response.choices[0].message.content or ""


def _gemini_chat(messages: list[dict], model: str = "gemini-2.5-flash") -> str:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(model)

    # Flatten to a single prompt — Gemini's chat API differs enough from OpenAI-style
    # messages that a plain concatenation is the simplest reliable fallback here.
    prompt_parts = []
    for m in messages:
        role = m["role"]
        prompt_parts.append(f"[{role.upper()}]\n{m['content']}")
    prompt = "\n\n".join(prompt_parts)

    # Without a timeout a hung call blocks the caller (e.g. document processing) forever.
    response = gemini_model.generate_content(prompt, request_options={"timeout": 60})
    return response.text or ""


def chat_completion(
    messages: list[dict],
    model: str = "openai/gpt-oss-120b",
    temperature: float = 0.2,
    purpose: str = "llm",
    user_id=None,
    groq_extra: dict | None = None,
) -> str:
    """Call Groq; on failure/rate-limit, retry once with Gemini as a fallback.

    `groq_extra` passes extra Groq-only request options, e.g. {"reasoning_effort": "low"} for
    the gpt-oss reasoning models, which otherwise can spend their whole token budget "thinking"
    on a large prompt and return an empty answer. (Ignored by the Gemini fallback.)"""
    try:
        with log_api_call("groq", purpose, user_id=user_id):
            reply = _groq_chat(model, messages, temperature, groq_extra)
            if not reply.strip():
                raise RuntimeError("Groq returned an empty reply")  # fall through to the fallback
            return reply
    except Exception:
        logger.warning("Groq call failed, falling back to Gemini", exc_info=True)
        try:
            with log_api_call("gemini", purpose, user_id=user_id):
                return _gemini_chat(messages)
        except Exception:
            logger.exception("Gemini fallback also failed")
            raise
