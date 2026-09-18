import json
from unittest.mock import MagicMock, patch

import pytest

from api._lib.result_store import get_latest_result, save_latest_result

SAMPLE_RESULT = {
    "clusters": [{"cluster_id": 1, "theme": "Billing & Payment Issues", "ticket_count": 4}],
    "total_tickets": 4,
}


def _fake_kv_response(result):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({"result": result}).encode("utf-8")
    return response


@pytest.fixture(autouse=True)
def kv_env(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://example-kv.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "fake-token")


def test_get_latest_returns_none_when_kv_not_configured(monkeypatch):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    assert get_latest_result() is None


def test_get_latest_returns_none_when_nothing_stored_yet():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response(None)):
        assert get_latest_result() is None


def test_get_latest_returns_stored_result():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response(json.dumps(SAMPLE_RESULT))):
        assert get_latest_result() == SAMPLE_RESULT


def test_get_latest_returns_none_on_malformed_stored_json():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response("not json")):
        assert get_latest_result() is None


def test_get_latest_returns_none_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        assert get_latest_result() is None


def test_save_latest_does_not_raise_when_kv_not_configured(monkeypatch):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    save_latest_result(SAMPLE_RESULT)  # must not raise


def test_save_latest_does_not_raise_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        save_latest_result(SAMPLE_RESULT)  # must not raise


def test_save_latest_writes_the_given_result():
    with patch("urllib.request.urlopen", return_value=_fake_kv_response("OK")) as mock_urlopen:
        save_latest_result(SAMPLE_RESULT)

    request = mock_urlopen.call_args.args[0]
    command = json.loads(request.data)
    assert command[0] == "SET"
    assert json.loads(command[2]) == SAMPLE_RESULT
