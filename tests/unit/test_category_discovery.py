import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from api._lib.category_discovery import discover_category, parse_discovery_response

KEYWORDS = ["frobnicate", "widget sync"]
TICKETS = [
    {"subject": "Widget sync fails after frobnicate step", "resolution": "Reran the sync job"},
    {"subject": "Frobnicate step hangs", "resolution": "Restarted the worker"},
]


def _fake_client(response_text):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=response_text)
    return client


def _valid_payload(**overrides):
    payload = {
        "label": "Widget Sync & Frobnicate Failures",
        "keywords": ["frobnicate", "widget sync"],
    }
    payload.update(overrides)
    return payload


def test_parses_valid_json_response():
    result = parse_discovery_response(json.dumps(_valid_payload()))
    assert result["label"] == _valid_payload()["label"]
    assert result["keywords"] == _valid_payload()["keywords"]


def test_parses_response_wrapped_in_code_fence():
    text = f"```json\n{json.dumps(_valid_payload())}\n```"
    result = parse_discovery_response(text)
    assert result["label"] == _valid_payload()["label"]


def test_rejects_response_missing_label():
    import pytest

    with pytest.raises(ValueError):
        parse_discovery_response(json.dumps(_valid_payload(label="")))


def test_rejects_response_with_non_list_keywords():
    import pytest

    with pytest.raises(ValueError):
        parse_discovery_response(json.dumps(_valid_payload(keywords="not a list")))


def test_discover_uses_client_response_when_valid():
    client = _fake_client(json.dumps(_valid_payload()))
    result = discover_category(KEYWORDS, TICKETS, client=client)
    assert result["label"] == _valid_payload()["label"]
    assert client.models.generate_content.call_count == 1


def test_discover_retries_once_then_returns_none_on_malformed_response():
    client = _fake_client("not json at all")
    result = discover_category(KEYWORDS, TICKETS, client=client, max_attempts=2)
    assert client.models.generate_content.call_count == 2
    assert result is None


def test_discover_returns_none_when_no_client_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = discover_category(KEYWORDS, TICKETS, client=None)
    assert result is None


def test_discover_returns_none_when_client_construction_raises(monkeypatch):
    """A broken google-genai install must degrade to None, not crash the
    whole /api/faqs/generate request."""
    import api._lib.category_discovery as category_discovery_module

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        category_discovery_module,
        "_get_client",
        lambda: (_ for _ in ()).throw(ImportError("DLL load failed")),
    )
    result = discover_category(KEYWORDS, TICKETS, client=None)
    assert result is None
