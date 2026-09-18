"""A small seeded/default ticket set, backed by Vercel KV (the same backend
as category_store.py, via kv_store.py), so the app has something to show
without requiring a CSV upload first - "the app isn't empty on first load."

This does NOT bring back the database that was removed in the stateless
migration (see docs/03-architecture.md). POST /api/faqs/generate still
takes an uploaded CSV and does everything in one request, with nothing
persisted. This store holds exactly one thing - a demo ticket set - seeded
once from the bundled data/sample_tickets.csv and served from KV after
that. If KV isn't configured (or the read/write fails), it falls back to
reading the bundled CSV fresh every call, so the sample set is available
either way - KV just avoids re-parsing the file on every request.
"""

import json
import os
from typing import Any, Dict, List

from .csv_ingest import parse_tickets_csv
from .kv_store import KVStoreError, kv_command

SEEDED_TICKETS_KEY = "ticket_faq:seeded_tickets"

_SAMPLE_CSV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_tickets.csv")
)


def _read_bundled_sample() -> List[Dict[str, Any]]:
    try:
        with open(_SAMPLE_CSV_PATH, "rb") as f:
            content = f.read()
    except OSError:
        return []
    try:
        return parse_tickets_csv(content)
    except ValueError:
        return []


def get_seeded_tickets() -> List[Dict[str, Any]]:
    """The current seeded demo ticket set: whatever's stored in KV, or the
    bundled sample CSV (seeded into KV for next time) if KV is empty or
    unavailable. Never raises - an empty result just means no demo data is
    available, which the caller should treat like "no tickets yet," not an
    error.
    """
    try:
        raw = kv_command(["GET", SEEDED_TICKETS_KEY])
    except KVStoreError:
        raw = None

    if raw:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, list) and data:
            return data

    tickets = _read_bundled_sample()
    if tickets:
        try:
            kv_command(["SET", SEEDED_TICKETS_KEY, json.dumps(tickets)])
        except KVStoreError:
            pass  # KV unavailable - still return the freshly-read tickets below
    return tickets
