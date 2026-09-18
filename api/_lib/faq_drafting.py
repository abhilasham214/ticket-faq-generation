"""Gemini is used for exactly one job in this app: drafting the FAQ text for
every already-formed, already-named cluster from one /api/faqs/generate
request - in a SINGLE Gemini call for the whole batch, not one call per
cluster. Clustering (clustering.py) and theme naming (cluster_naming.py) are
both deterministic and Gemini-free.

One call per cluster meant a 5-cluster CSV made 5 separate requests, which
burns through the free API tier's request quota fast (a 429
RESOURCE_EXHAUSTED after a handful of test runs is what motivated this) -
batching all clusters into one prompt/response turns that into 1 request
regardless of cluster count.

The Gemini response is validated before use, and any failure - no API key,
network error, timeout, malformed JSON, wrong number of entries, a missing/
duplicate/invalid cluster_index, missing fields on any entry - falls back to
a deterministic template built only from each cluster's own tickets, for
every cluster in the batch. The app never crashes or 500s because of a bad/
unavailable Gemini response.

Every returned FAQ dict carries a `gemini_generated` flag (True from a real
parsed response, False from `template_fallback`) so the caller/UI can show
when a batch quietly degraded to templates instead of it looking identical
to a normal Gemini-drafted result.
"""

import json
import os
from typing import Any, Dict, List, Optional

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

REQUIRED_STRING_FIELDS = ("question", "answer")

PROMPT_INSTRUCTIONS = """You are writing an internal technical/support knowledge-base FAQ.

You will be given several independent clusters of resolved support tickets, each already
grouped by recurring issue and already named. Draft exactly ONE FAQ entry per cluster below.

For every cluster, treat it as fully independent from the others:
Use ONLY the information contained in that cluster's own supplied tickets.
Do not invent causes, troubleshooting steps, systems, configurations, or solutions that are not supported by its tickets.
Do not mix information from one cluster into another cluster's FAQ entry.

Synthesize the recurring pattern across a cluster's tickets rather than copying one ticket.

Each FAQ entry must contain:
1. A natural question that a support/engineering team member might actually search for.
2. A concise answer explaining the recurring issue.
3. Practical resolution steps based only on that cluster's supplied resolutions.
4. Escalation guidance only when supported by that cluster's source tickets.

The question should describe the actual recurring issue.
Do NOT generate questions such as: "How do I resolve issues related to X?"

Avoid generic wording. Make each FAQ specific and actionable.
If a cluster's tickets do not contain enough information to make a claim, do not invent it."""


def _get_client():
    """Lazily build a Gemini client. Returns None if no API key is configured,
    so callers fall back to the template drafter instead of crashing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    from google import genai  # imported lazily so tests never need the package installed

    return genai.Client(api_key=api_key)


def _build_prompt(entries: List[Dict[str, Any]]) -> str:
    lines = [
        PROMPT_INSTRUCTIONS,
        "",
        f"There are {len(entries)} clusters below, indexed 0 to {len(entries) - 1}.",
    ]
    for i, entry in enumerate(entries):
        cluster = entry["cluster"]
        lines += [
            "",
            f"=== Cluster {i} ===",
            f"Theme: {entry['theme']}",
            f"Common keywords: {', '.join(cluster.get('keywords', [])) or 'n/a'}",
            "Resolved tickets:",
        ]
        for t in entry["tickets"]:
            lines.append(f"- Title: {t['subject']}")
            if t.get("description"):
                lines.append(f"  Description: {t['description']}")
            lines.append(f"  Resolution: {t['resolution']}")

    lines += [
        "",
        f"Return ONLY a JSON array with exactly {len(entries)} objects, no markdown fences, no extra text.",
        "Each object must have exactly these keys:",
        '  "cluster_index": the integer index of the cluster this entry is for (matching "=== Cluster N ===" above),',
        "  \"question\": a specific question describing that cluster's actual recurring issue,",
        "  \"answer\": a concise 2-4 sentence answer explaining that cluster's recurring issue,",
        "  \"resolution_steps\": an array of short, practical steps grounded only in that cluster's resolutions above,",
        "  \"escalation\": escalation guidance as a string if supported by that cluster's tickets, otherwise an empty string,",
    ]
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _validate_faq_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_STRING_FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        raise ValueError(f"Response missing fields: {', '.join(missing)}")

    steps_raw = data.get("resolution_steps", [])
    if not isinstance(steps_raw, list):
        raise ValueError("resolution_steps must be a list of strings.")
    resolution_steps = [str(s).strip() for s in steps_raw if str(s).strip()]

    return {
        "question": str(data["question"]).strip(),
        "answer": str(data["answer"]).strip(),
        "resolution_steps": resolution_steps,
        "escalation": str(data.get("escalation") or "").strip(),
        "gemini_generated": True,
    }


def parse_faqs_response(text: str, expected_count: int) -> List[Dict[str, Any]]:
    """Validate and normalize a raw Gemini batch response into `expected_count`
    FAQ dicts, reordered to match the input clusters via each entry's
    "cluster_index" (so the result is correct even if Gemini returns the
    entries out of order).

    Raises ValueError on anything that doesn't meet the contract - not a
    JSON array, wrong entry count, a missing/duplicate/out-of-range
    cluster_index, or a malformed entry - so the caller can fall back to
    deterministic templates for the whole batch.
    """
    data = json.loads(_strip_code_fence(text))
    if not isinstance(data, list):
        raise ValueError("Response was not a JSON array.")
    if len(data) != expected_count:
        raise ValueError(f"Expected {expected_count} entries, got {len(data)}.")

    by_index: Dict[int, Dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Array entry was not a JSON object.")
        idx = item.get("cluster_index")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx in by_index:
            raise ValueError("Array entry has a missing, duplicate, or non-integer 'cluster_index'.")
        by_index[idx] = _validate_faq_fields(item)

    if set(by_index) != set(range(expected_count)):
        raise ValueError("cluster_index values did not cover 0..N-1 exactly once.")

    return [by_index[i] for i in range(expected_count)]


def template_fallback(
    theme: str, cluster: Dict[str, Any], tickets: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Deterministic FAQ built only from the cluster's own data - used when
    Gemini is unavailable or its response fails validation. Every field is
    grounded directly in the source tickets; nothing is invented.
    """
    resolutions: List[str] = []
    seen = set()
    for t in tickets:
        resolution = (t.get("resolution") or "").strip()
        if resolution and resolution not in seen:
            resolutions.append(resolution)
            seen.add(resolution)

    first_subject = tickets[0]["subject"].strip() if tickets else theme
    question = f'What should I do about recurring "{theme}" reports like "{first_subject}"?'
    answer = (
        f"This is a recurring {theme.lower()} pattern seen across {len(tickets)} resolved "
        f"tickets in this batch. Past resolution: {resolutions[0]}"
        if resolutions
        else f"This is a recurring {theme.lower()} pattern seen across {len(tickets)} resolved tickets."
    )

    return {
        "question": question,
        "answer": answer,
        "resolution_steps": resolutions[:5],
        "escalation": "",
        "gemini_generated": False,
    }


def draft_faqs_for_clusters(
    entries: List[Dict[str, Any]],
    client: Optional[Any] = None,
    max_attempts: int = 2,
) -> List[Dict[str, Any]]:
    """Draft one FAQ per cluster via a SINGLE Gemini call for the whole batch,
    falling back to per-cluster deterministic templates for every cluster if
    that call or its response fails validation in any way.

    Each entry in `entries` must be {"theme": str, "cluster": {...}, "tickets": [...]}.
    `client` can be injected (e.g. a mock) for testing; otherwise a real
    Gemini client is built from GEMINI_API_KEY. Returns a list of FAQ dicts
    in the same order as `entries`. The real API is never called in unit tests.
    """
    fallback_all = [template_fallback(e["theme"], e["cluster"], e["tickets"]) for e in entries]
    if not entries:
        return fallback_all

    try:
        active_client = client if client is not None else _get_client()
    except Exception:
        # Building the client can fail for reasons that have nothing to do
        # with the API call itself (e.g. a broken google-genai/cryptography
        # install) - that must degrade to the template fallback too, not
        # crash the whole /api/faqs/generate request.
        active_client = None
    if active_client is None:
        return fallback_all

    prompt = _build_prompt(entries)

    for attempt in range(max_attempts):
        try:
            response = active_client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
            return parse_faqs_response(response.text, len(entries))
        except Exception:
            if attempt == max_attempts - 1:
                return fallback_all

    return fallback_all
