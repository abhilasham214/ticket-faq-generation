import json
from unittest.mock import MagicMock, patch

import pytest

from api._lib.category_store import (
    CategoryStoreError,
    add_custom_category,
    list_custom_categories,
)


def _fake_kv_response(result):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({"result": result}).encode("utf-8")
    return response


@pytest.fixture(autouse=True)
def kv_env(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://example-kv.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "fake-token")


def test_list_returns_empty_when_kv_not_configured(monkeypatch):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    assert list_custom_categories() == []


def test_list_returns_empty_when_nothing_stored_yet():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response(None)):
        assert list_custom_categories() == []


def test_list_returns_stored_categories():
    stored = [{"id": "custom_widget_sync_1", "label": "Widget Sync Failures", "keywords": ["widget sync"]}]
    with patch("urllib.request.urlopen", return_value=_fake_kv_response(json.dumps(stored))):
        assert list_custom_categories() == stored


def test_list_returns_empty_on_malformed_stored_json():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response("not json")):
        assert list_custom_categories() == []


def test_list_returns_empty_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        assert list_custom_categories() == []


def test_add_custom_category_persists_full_list():
    existing = [{"id": "custom_a_1", "label": "A", "keywords": ["a"]}]

    responses = [_fake_kv_response(json.dumps(existing)), _fake_kv_response("OK")]
    with patch("urllib.request.urlopen", side_effect=responses) as mock_urlopen:
        entry = add_custom_category("Widget Sync Failures", ["Widget Sync", " frobnicate "])

    assert entry["label"] == "Widget Sync Failures"
    assert entry["keywords"] == ["widget sync", "frobnicate"]
    assert entry["id"].startswith("custom_")

    set_call = mock_urlopen.call_args_list[1]
    set_request = set_call.args[0]
    command = json.loads(set_request.data)
    assert command[0] == "SET"
    saved_list = json.loads(command[2])
    assert saved_list == existing + [entry]


def test_add_custom_category_raises_when_kv_not_configured(monkeypatch):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    with pytest.raises(CategoryStoreError):
        add_custom_category("Widget Sync Failures", ["widget sync"])


def test_add_custom_category_rejects_empty_label():
    with pytest.raises(ValueError):
        add_custom_category("   ", ["widget sync"])


def test_add_custom_category_raises_when_write_fails():
    with patch("urllib.request.urlopen", side_effect=[_fake_kv_response(None), OSError("boom")]):
        with pytest.raises(CategoryStoreError):
            add_custom_category("Widget Sync Failures", ["widget sync"])
