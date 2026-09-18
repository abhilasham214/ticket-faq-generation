import json
import os
from typing import Any, Dict, List, Optional

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

REQUIRED_FIELDS = ("theme_title", "question", "answer")


def _get_client():
    """Lazily build a Gemini client. Returns None if no API key is configured,
    so callers fall back to the template drafter instead of crashing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    from google import genai  # imported lazily so tests never need the package installed

    return genai.Client(api_key=api_key)


def _build_prompt(cluster: Dict[str, Any], tickets: List[Dict[str, Any]]) -> str:
    lines = [
        "You are drafting one FAQ entry for a support team's internal knowledge base.",
        "All of the tickets below were independently resolved but share the same recurring issue theme.",
        f"Top keywords for this theme: {', '.join(cluster.get('top_terms', [])) or 'n/a'}",
        "",
        "Resolved tickets:",
    ]
    for t in tickets:
        lines.append(f"- Subject: {t['subject']}")
        lines.append(f"  Description: {t['description']}")
        lines.append(f"  Resolution: {t['resolution']}")

    lines += [
        "",
        "Return ONLY a JSON object with exactly these keys, no markdown fences, no extra text:",
        '  "theme_title": a short 3-6 word name for this recurring theme,',
        '  "question": a single practical question a support agent or user would search for,',
        '  "answer": a clear, actionable 2-4 sentence answer grounded in the resolutions above.',
    ]
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def parse_faq_response(text: str) -> Dict[str, str]:
    data = json.loads(_strip_code_fence(text))
    if not isinstance(data, dict):
        raise ValueError("Response was not a JSON object.")

    missing = [field for field in REQUIRED_FIELDS if not str(data.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Response missing fields: {', '.join(missing)}")

    return {field: str(data[field]).strip() for field in REQUIRED_FIELDS}


def template_fallback(cluster: Dict[str, Any], tickets: List[Dict[str, Any]]) -> Dict[str, str]:
    top_terms = cluster.get("top_terms") or []
    theme_title = " / ".join(term.title() for term in top_terms[:3]) or "Recurring Issue"
    question = f"How do I resolve issues related to {theme_title.lower()}?"
    answer = (
        tickets[0]["resolution"]
        if tickets
        else "Refer to the linked tickets for the resolution steps that applied."
    )
    return {"theme_title": theme_title, "question": question, "answer": answer}


def draft_faq_for_cluster(
    cluster: Dict[str, Any],
    tickets: List[Dict[str, Any]],
    client: Optional[Any] = None,
    max_attempts: int = 2,
) -> Dict[str, str]:
    """Draft one FAQ entry for a cluster via Gemini, falling back to a template on any failure.

    `client` can be injected (e.g. a mock) for testing; otherwise a real Gemini client is
    built from GEMINI_API_KEY. The real API is never called in unit tests.
    """
    active_client = client if client is not None else _get_client()
    if active_client is None:
        return template_fallback(cluster, tickets)

    prompt = _build_prompt(cluster, tickets)

    for attempt in range(max_attempts):
        try:
            response = active_client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
            return parse_faq_response(response.text)
        except Exception:
            if attempt == max_attempts - 1:
                return template_fallback(cluster, tickets)

    return template_fallback(cluster, tickets)
