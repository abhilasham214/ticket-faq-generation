"""Persistent storage for user-approved custom categories, backed by Vercel
KV (Upstash Redis REST API) so an "add as new domain" decision made in the
frontend popup survives across deployments and serverless cold starts -
unlike the rest of this app's request-scoped state (see
docs/03-architecture.md's "no database" reasoning, which still holds for
ticket data itself; this is one of a couple of pieces of state a human
explicitly decided should persist - see also ticket_store.py).

Shares its KV REST client with ticket_store.py via kv_store.py.
"""

import json
from typing import Any, Dict, List

from .kv_store import KVStoreError, kv_command

CUSTOM_CATEGORIES_KEY = "ticket_faq:custom_categories"

# Re-exported so existing callers/tests can keep importing CategoryStoreError
# from this module without needing to know it's shared with ticket_store.py.
CategoryStoreError = KVStoreError


def _slugify(label: str) -> str:
    slug = "_".join(label.lower().split())
    return "".join(ch for ch in slug if ch.isalnum() or ch == "_")[:40] or "category"


def list_custom_categories() -> List[Dict[str, Any]]:
    """Every custom category a user has approved via the frontend popup, each
    shaped like {"id", "label", "keywords"}.

    Returns an empty list if KV isn't configured or nothing has been added
    yet - callers (clustering/naming) should treat "no custom categories" as
    the normal case, not an error, so this never raises.
    """
    try:
        raw = kv_command(["GET", CUSTOM_CATEGORIES_KEY])
    except CategoryStoreError:
        return []
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def add_custom_category(label: str, keywords: List[str]) -> Dict[str, Any]:
    """Append a new custom category and persist the full list back to KV.

    Unlike `list_custom_categories`, this raises CategoryStoreError if KV
    isn't configured or the write fails - the caller (the /api/categories
    endpoint) should surface that as a real error rather than silently
    pretending the user's "add as new domain" choice was saved.
    """
    label = label.strip()
    if not label:
        raise ValueError("label must not be empty.")

    existing = list_custom_categories()
    clean_keywords = [k.strip().lower() for k in keywords if k.strip()]
    category_id = f"custom_{_slugify(label)}_{len(existing) + 1}"
    entry = {"id": category_id, "label": label, "keywords": clean_keywords}

    updated = existing + [entry]
    kv_command(["SET", CUSTOM_CATEGORIES_KEY, json.dumps(updated)])
    return entry
