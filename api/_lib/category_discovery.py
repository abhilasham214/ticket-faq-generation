"""Gemini-assisted naming for clusters that don't match the curated domain
taxonomy in domain_categories.py.

Clustering (clustering.py) and the curated-category path in cluster_naming.py
stay fully deterministic and LLM-free, exactly as documented there. This
module is only consulted by the caller (api/index.py) for a cluster whose
top keywords matched none of CATEGORIES - i.e. a genuinely new recurring
theme, not one of the 5 curated support domains.

Same never-crash contract as faq_drafting.py: no API key, a network error,
a timeout, or a malformed/invalid response all degrade to `None`, and the
caller falls back to cluster_naming's deterministic `_fallback_name` result.
The app never crashes or 500s because Gemini is unavailable.

This module does NOT mutate CATEGORIES - a Gemini-suggested label is used
for that one response only. Promoting a recurring discovered theme into a
permanent curated category (with its keyword-bridging boost in clustering.py)
is still a deliberate manual edit to domain_categories.py, so the taxonomy
never silently drifts from a model's one-off guess.
"""

import json
import os
from typing import Any, Dict, List, Optional

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

PROMPT_INSTRUCTIONS = """You are naming a cluster of related customer support tickets for an internal FAQ knowledge base.

Use ONLY the supplied keywords and ticket subjects to infer the theme.
Do not invent an issue category that isn't supported by the given terms.

Produce a short, specific, title-case theme name (3-7 words) in the same
style as existing categories, e.g. "Billing & Duplicate Charge Issues",
"SSO Authentication & Certificate Issues", "API Authentication & Rate Limit Issues".

Also produce a short list (3-6) of lowercase trigger keywords/phrases that
future clusters about this same issue would likely also contain."""


def _get_client():
    """Lazily build a Gemini client. Returns None if no API key is configured,
    so callers fall back to the deterministic name instead of crashing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    from google import genai  # imported lazily so tests never need the package installed

    return genai.Client(api_key=api_key)


def _build_prompt(keywords: List[str], tickets: List[Dict[str, Any]]) -> str:
    lines = [
        PROMPT_INSTRUCTIONS,
        "",
        f"Cluster keywords: {', '.join(keywords) or 'n/a'}",
        "",
        "Ticket subjects in this cluster:",
    ]
    for t in tickets:
        lines.append(f"- {t['subject']}")

    lines += [
        "",
        "Return ONLY a JSON object with exactly these keys, no markdown fences, no extra text:",
        '  "label": the theme name string,',
        '  "keywords": an array of 3-6 lowercase trigger keyword/phrase strings,',
    ]
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def parse_discovery_response(text: str) -> Dict[str, Any]:
    """Validate and normalize a raw Gemini response into the discovery shape.

    Raises ValueError on anything that doesn't meet the contract, so the
    caller can fall back to the deterministic name.
    """
    data = json.loads(_strip_code_fence(text))
    if not isinstance(data, dict):
        raise ValueError("Response was not a JSON object.")

    label = str(data.get("label", "")).strip()
    if not label:
        raise ValueError("Response missing 'label'.")

    keywords_raw = data.get("keywords", [])
    if not isinstance(keywords_raw, list):
        raise ValueError("'keywords' must be a list of strings.")
    keywords = [str(k).strip().lower() for k in keywords_raw if str(k).strip()]

    return {"label": label, "keywords": keywords}


def discover_category(
    keywords: List[str],
    tickets: List[Dict[str, Any]],
    client: Optional[Any] = None,
    max_attempts: int = 2,
) -> Optional[Dict[str, Any]]:
    """Ask Gemini to name an uncurated cluster from its own keywords/tickets.

    `client` can be injected (e.g. a mock) for testing; otherwise a real
    Gemini client is built from GEMINI_API_KEY. Returns None on any failure
    (no key, network error, malformed JSON, missing fields) so the caller
    can fall back to cluster_naming's deterministic `_fallback_name`.
    """
    try:
        active_client = client if client is not None else _get_client()
    except Exception:
        # Building the client can fail for reasons unrelated to the API call
        # itself (e.g. a broken google-genai/cryptography install) - that
        # must degrade gracefully too, not crash the whole request.
        active_client = None
    if active_client is None:
        return None

    prompt = _build_prompt(keywords, tickets)

    for attempt in range(max_attempts):
        try:
            response = active_client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
            return parse_discovery_response(response.text)
        except Exception:
            if attempt == max_attempts - 1:
                return None

    return None
