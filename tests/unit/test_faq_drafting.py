import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from api._lib.faq_drafting import draft_faq_for_cluster, parse_faq_response, template_fallback

CLUSTER = {"top_terms": ["login", "password", "reset"]}
TICKETS = [
    {
        "subject": "Cannot log in",
        "description": "Password rejected after reset",
        "resolution": "Cleared stale session cookie",
    }
]


def _fake_client(response_text):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=response_text)
    return client


def test_parses_valid_json_response():
    text = json.dumps(
        {
            "theme_title": "Login Issues",
            "question": "Why can't I log in after resetting my password?",
            "answer": "Clear your session and log in again with the new password.",
        }
    )
    result = parse_faq_response(text)
    assert result["theme_title"] == "Login Issues"


def test_parses_response_wrapped_in_code_fence():
    payload = json.dumps({"theme_title": "Login Issues", "question": "Q?", "answer": "A."})
    text = f"```json\n{payload}\n```"
    result = parse_faq_response(text)
    assert result["question"] == "Q?"


def test_draft_uses_client_response_when_valid():
    payload = json.dumps({"theme_title": "Login Issues", "question": "Q?", "answer": "A."})
    client = _fake_client(payload)
    result = draft_faq_for_cluster(CLUSTER, TICKETS, client=client)
    assert result["theme_title"] == "Login Issues"
    assert client.models.generate_content.call_count == 1


def test_draft_retries_once_then_falls_back_on_malformed_response():
    client = _fake_client("not json at all")
    result = draft_faq_for_cluster(CLUSTER, TICKETS, client=client, max_attempts=2)
    assert client.models.generate_content.call_count == 2
    assert result == template_fallback(CLUSTER, TICKETS)


def test_draft_falls_back_when_no_client_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = draft_faq_for_cluster(CLUSTER, TICKETS, client=None)
    assert result == template_fallback(CLUSTER, TICKETS)


def test_template_fallback_is_grounded_in_first_ticket_resolution():
    result = template_fallback(CLUSTER, TICKETS)
    assert result["answer"] == TICKETS[0]["resolution"]
