import json
from unittest.mock import MagicMock, patch

import pytest

from api._lib.ticket_store import get_seeded_tickets

SAMPLE_TICKETS = [
    {"external_id": "T1", "subject": "Cannot log in", "description": "", "resolution": "Reset session cookie"},
    {"external_id": "T2", "subject": "Invoice duplicate", "description": "", "resolution": "Refunded charge"},
    {"external_id": "T3", "subject": "API 429 errors", "description": "", "resolution": "Fixed rate limiter"},
]


def _fake_kv_response(result):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({"result": result}).encode("utf-8")
    return response


@pytest.fixture(autouse=True)
def kv_env(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://example-kv.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "fake-token")


def test_returns_tickets_already_stored_in_kv():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response(json.dumps(SAMPLE_TICKETS))):
        assert get_seeded_tickets() == SAMPLE_TICKETS


def test_seeds_from_bundled_csv_when_kv_empty():
    responses = [_fake_kv_response(None), _fake_kv_response("OK")]
    with patch("urllib.request.urlopen", side_effect=responses):
        tickets = get_seeded_tickets()
    assert len(tickets) >= 3
    assert all({"external_id", "subject", "description", "resolution"} <= t.keys() for t in tickets)


def test_falls_back_to_bundled_csv_when_kv_not_configured(monkeypatch):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    tickets = get_seeded_tickets()
    assert len(tickets) >= 3


def test_falls_back_to_bundled_csv_on_kv_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        tickets = get_seeded_tickets()
    assert len(tickets) >= 3


def test_falls_back_to_bundled_csv_on_malformed_stored_json():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response("not json")):
        tickets = get_seeded_tickets()
    assert len(tickets) >= 3


def test_does_not_fail_when_kv_write_back_fails_after_seeding():
    responses = [_fake_kv_response(None), OSError("boom")]
    with patch("urllib.request.urlopen", side_effect=responses):
        tickets = get_seeded_tickets()
    assert len(tickets) >= 3
