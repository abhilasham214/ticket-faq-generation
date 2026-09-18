"""Persists the most recent /api/faqs/generate (or .../generate/sample)
result in Vercel KV, so a fresh visit shows what was last generated instead
of an empty state - "the seeded data or the previous data should be there
when opened."

There's still no per-user session or accounts (see docs/01-problem-and-
scope.md), so this is one global "latest result" shared by every visitor,
not per-user history - consistent with the app's existing "each generate
run replaces the previous batch wholesale" stance, just now surviving a
reload/new visit instead of only lasting one browser tab.
"""

import json
from typing import Any, Dict, Optional

from .kv_store import KVStoreError, kv_command

LATEST_RESULT_KEY = "ticket_faq:latest_result"


def get_latest_result() -> Optional[Dict[str, Any]]:
    """The last generated result (a GenerateResponse-shaped dict), or None if
    KV isn't configured, unreachable, or nothing has been generated yet.
    """
    try:
        raw = kv_command(["GET", LATEST_RESULT_KEY])
    except KVStoreError:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def save_latest_result(result: Dict[str, Any]) -> None:
    """Best-effort - a failed save here must never fail the generate request
    that produced `result`. The caller already has the response it needs to
    return to its own client either way.
    """
    try:
        kv_command(["SET", LATEST_RESULT_KEY, json.dumps(result)])
    except KVStoreError:
        pass
