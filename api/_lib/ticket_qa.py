"""Gemini-backed, single-ticket Q&A ("Discuss" on a source ticket) -
grounded only in that one ticket's own subject/description/resolution, with
no cross-ticket or cross-theme context.

No template fallback here, unlike faq_drafting.py/category_discovery.py: an
open-ended question has no safe deterministic answer the way a templated
FAQ does. Any failure (no API key, network error, malformed response) is
surfaced to the caller as None, which the /api/tickets/ask endpoint turns
into a 503 - an honest "investigation unavailable" rather than a guessed
answer.
"""

import json
import os
from typing import Any, Dict, Optional

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

PROMPT_INSTRUCTIONS = """You are answering a support engineer's question about ONE specific resolved ticket.

Use ONLY the information in the ticket below. Do not invent causes, systems,
configurations, or steps that aren't present in its subject, description, or
resolution. Do not reference any other ticket - you were given exactly one.

If the ticket doesn't contain enough information to answer the question,
say so plainly instead of guessing (e.g. "The ticket doesn't mention that.").

Keep the answer concise (1-4 sentences) and specific to this ticket."""


def _get_client():
    """Lazily build a Gemini client. Returns None if no API key is configured,
    so callers surface "investigation unavailable" instead of crashing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    from google import genai  # imported lazily so tests never need the package installed

    return genai.Client(api_key=api_key)


def _build_prompt(ticket: Dict[str, Any], question: str) -> str:
    lines = [
        PROMPT_INSTRUCTIONS,
        "",
        f"Ticket subject: {ticket['title']}",
    ]
    if ticket.get("description"):
        lines.append(f"Ticket description: {ticket['description']}")
    lines.append(f"Ticket resolution: {ticket['resolution']}")
    lines += [
        "",
        f"Question: {question}",
        "",
        "Return ONLY a JSON object with exactly this key, no markdown fences, no extra text:",
        '  "answer": your answer as a string,',
    ]
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def parse_answer_response(text: str) -> Dict[str, str]:
    """Validate and normalize a raw Gemini response into {"answer": str}.

    Raises ValueError on anything that doesn't meet the contract, so the
    caller can treat it the same as any other failure (return None).
    """
    data = json.loads(_strip_code_fence(text))
    if not isinstance(data, dict):
        raise ValueError("Response was not a JSON object.")

    answer = str(data.get("answer", "")).strip()
    if not answer:
        raise ValueError("Response missing 'answer'.")

    return {"answer": answer}


def ask_about_ticket(
    ticket: Dict[str, Any],
    question: str,
    client: Optional[Any] = None,
    max_attempts: int = 2,
) -> Optional[Dict[str, str]]:
    """Answer a free-text question grounded only in one ticket's own fields.

    `client` can be injected (e.g. a mock) for testing; otherwise a real
    Gemini client is built from GEMINI_API_KEY. Returns {"answer": str} on
    success, or None on any failure (no key, network error, malformed
    response) - there's no deterministic template fallback for an
    open-ended question, so the caller should surface None as "unavailable"
    rather than inventing an answer.
    """
    try:
        active_client = client if client is not None else _get_client()
    except Exception:
        # Building the client can fail for reasons unrelated to the API call
        # itself (e.g. a broken google-genai/cryptography install).
        active_client = None
    if active_client is None:
        return None

    prompt = _build_prompt(ticket, question)

    for attempt in range(max_attempts):
        try:
            response = active_client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
            return parse_answer_response(response.text)
        except Exception:
            if attempt == max_attempts - 1:
                return None

    return None
