"""Thin shared client over Vercel KV's (Upstash Redis) REST command
endpoint, used by every KV-backed store in this app (category_store.py,
ticket_store.py). Uses stdlib urllib instead of an added HTTP client
dependency - one small JSON request either way, and it keeps the
serverless function's cold-start footprint unchanged.

Requires KV_REST_API_URL and KV_REST_API_TOKEN (auto-injected by Vercel once
a KV store is attached to the project; see .env.example for local dev).
"""

import json
import os
import urllib.request
from typing import Any, List, Optional, Tuple

_REQUEST_TIMEOUT_SECONDS = 5


class KVStoreError(RuntimeError):
    pass


def kv_config() -> Optional[Tuple[str, str]]:
    url = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if not url or not token:
        return None
    return url, token


def kv_command(command: List[Any]) -> Any:
    """Send one Upstash REST command (e.g. ["GET", key] or ["SET", key, value])
    and return its `result`. Raises KVStoreError on any failure - no config,
    network error, timeout, or an error field in the response.
    """
    config = kv_config()
    if config is None:
        raise KVStoreError("KV_REST_API_URL / KV_REST_API_TOKEN are not configured.")
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
        raise KVStoreError(f"KV request failed: {exc}") from exc

    if not isinstance(body, dict):
        raise KVStoreError("Unexpected KV response shape.")
    if body.get("error"):
        raise KVStoreError(f"KV error: {body['error']}")
    return body.get("result")
