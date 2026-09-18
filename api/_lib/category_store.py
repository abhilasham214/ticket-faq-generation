"""Persistent storage for user-approved custom categories, backed by Vercel
KV (Upstash Redis REST API) so an "add as new domain" decision made in the
frontend popup survives across deployments and serverless cold starts -
unlike the rest of this app's request-scoped state (see
docs/03-architecture.md's "no database" reasoning, which still holds for
ticket data itself; this is the one piece of state a human explicitly
decided should persist).

Uses stdlib urllib against Upstash's REST command endpoint instead of an
added HTTP client dependency - one small JSON request either way, and it
keeps the serverless function's cold-start footprint unchanged.

Requires KV_REST_API_URL and KV_REST_API_TOKEN (auto-injected by Vercel once
a KV store is attached to the project; see .env.example for local dev).
"""

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

CUSTOM_CATEGORIES_KEY = "ticket_faq:custom_categories"

_REQUEST_TIMEOUT_SECONDS = 5


class CategoryStoreError(RuntimeError):
    pass


def _kv_config() -> Optional[Tuple[str, str]]:
    url = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if not url or not token:
        return None
    return url, token


def _kv_command(command: List[Any]) -> Any:
    """Send one Upstash REST command (e.g. ["GET", key] or ["SET", key, value])
    and return its `result`. Raises CategoryStoreError on any failure - no
    config, network error, timeout, or an error field in the response.
    """
    config = _kv_config()
    if config is None:
        raise CategoryStoreError("KV_REST_API_URL / KV_REST_API_TOKEN are not configured.")
    url, token = config

    request = urllib.request.Request(
        url,
        data=json.dumps(command).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        # OSError covers urllib.error.URLError/HTTPError and raw socket/timeout
        # errors alike; ValueError covers a non-JSON response body.
        raise CategoryStoreError(f"KV request failed: {exc}") from exc

    if not isinstance(body, dict):
        raise CategoryStoreError("Unexpected KV response shape.")
    if body.get("error"):
        raise CategoryStoreError(f"KV error: {body['error']}")
    return body.get("result")


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
        raw = _kv_command(["GET", CUSTOM_CATEGORIES_KEY])
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
    _kv_command(["SET", CUSTOM_CATEGORIES_KEY, json.dumps(updated)])
    return entry
