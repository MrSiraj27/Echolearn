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
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def _groq_chat(model: str, messages: list[dict], temperature: float = 0.2) -> str:
    client = get_groq_client()
    response = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
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

    response = gemini_model.generate_content(prompt)
    return response.text or ""


def chat_completion(
    messages: list[dict],
    model: str = "openai/gpt-oss-120b",
    temperature: float = 0.2,
    purpose: str = "llm",
    user_id=None,
) -> str:
    """Call Groq; on failure/rate-limit, retry once with Gemini as a fallback."""
    try:
        with log_api_call("groq", purpose, user_id=user_id):
            return _groq_chat(model, messages, temperature)
    except Exception:
        logger.warning("Groq call failed, falling back to Gemini", exc_info=True)
        try:
            with log_api_call("gemini", purpose, user_id=user_id):
                return _gemini_chat(messages)
        except Exception:
            logger.exception("Gemini fallback also failed")
            raise
