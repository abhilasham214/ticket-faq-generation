import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from api._lib.ticket_qa import ask_about_ticket, parse_answer_response

TICKET = {
    "title": "API returns 429 errors during normal usage",
    "description": "Customer hit rate limits well under their plan's quota.",
    "resolution": "Fixed the rate limiter to key on (api_key, endpoint) instead of api_key alone.",
}


def _fake_client(response_text):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=response_text)
    return client


def test_parses_valid_json_response():
    result = parse_answer_response(json.dumps({"answer": "The rate limiter keyed on api_key alone."}))
    assert result["answer"] == "The rate limiter keyed on api_key alone."


def test_parses_response_wrapped_in_code_fence():
    text = f"```json\n{json.dumps({'answer': 'Grounded answer.'})}\n```"
    result = parse_answer_response(text)
    assert result["answer"] == "Grounded answer."


def test_rejects_response_missing_answer():
    import pytest

    with pytest.raises(ValueError):
        parse_answer_response(json.dumps({"answer": ""}))


def test_rejects_response_that_is_not_a_json_object():
    import pytest

    with pytest.raises(ValueError):
        parse_answer_response(json.dumps(["not", "an", "object"]))


def test_ask_uses_client_response_when_valid():
    client = _fake_client(json.dumps({"answer": "The rate limiter now keys on (api_key, endpoint)."}))
    result = ask_about_ticket(TICKET, "What was the root cause?", client=client)
    assert result == {"answer": "The rate limiter now keys on (api_key, endpoint)."}
    assert client.models.generate_content.call_count == 1


def test_ask_retries_once_then_returns_none_on_malformed_response():
    client = _fake_client("not json at all")
    result = ask_about_ticket(TICKET, "What was the root cause?", client=client, max_attempts=2)
    assert client.models.generate_content.call_count == 2
    assert result is None


def test_ask_returns_none_when_no_client_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = ask_about_ticket(TICKET, "What was the root cause?", client=None)
    assert result is None


def test_ask_returns_none_when_client_construction_raises(monkeypatch):
    """A broken google-genai install must degrade to None, not crash the
    whole /api/tickets/ask request."""
    import api._lib.ticket_qa as ticket_qa_module

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        ticket_qa_module,
        "_get_client",
        lambda: (_ for _ in ()).throw(ImportError("DLL load failed")),
    )
    result = ask_about_ticket(TICKET, "What was the root cause?", client=None)
    assert result is None
