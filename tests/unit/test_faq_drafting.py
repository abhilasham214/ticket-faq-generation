import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from api._lib.faq_drafting import draft_faqs_for_clusters, parse_faqs_response, template_fallback

THEME_A = "Password Reset & Account Recovery"
CLUSTER_A = {"keywords": ["password", "reset", "login"]}
TICKETS_A = [
    {
        "subject": "Cannot log in",
        "description": "Password rejected after reset",
        "resolution": "Cleared stale session cookie",
    },
    {
        "subject": "Locked out of account",
        "description": "",
        "resolution": "Manually unlocked the account",
    },
]

THEME_B = "Billing & Duplicate Charge Issues"
CLUSTER_B = {"keywords": ["invoice", "duplicate", "charge"]}
TICKETS_B = [
    {"subject": "Invoice shows duplicate charge", "description": "", "resolution": "Refunded the duplicate charge"},
]

ENTRIES = [
    {"theme": THEME_A, "cluster": CLUSTER_A, "tickets": TICKETS_A},
    {"theme": THEME_B, "cluster": CLUSTER_B, "tickets": TICKETS_B},
]


def _fake_client(response_text):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=response_text)
    return client


def _valid_faq(**overrides):
    payload = {
        "question": "Why do users get locked out after a password reset?",
        "answer": "A stale session cookie or a manual lock can block login right after a reset.",
        "resolution_steps": ["Clear the session cookie.", "Unlock the account if needed."],
        "escalation": "",
    }
    payload.update(overrides)
    return payload


def _valid_batch_payload():
    return [
        {"cluster_index": 0, **_valid_faq()},
        {
            "cluster_index": 1,
            "question": "Why do customers see a duplicate charge on their invoice?",
            "answer": "A retried webhook can double-charge before the refund is issued.",
            "resolution_steps": ["Refund the duplicate charge."],
            "escalation": "",
        },
    ]


def test_parses_valid_json_array_response():
    result = parse_faqs_response(json.dumps(_valid_batch_payload()), expected_count=2)
    assert result[0]["question"] == _valid_faq()["question"]
    assert result[1]["answer"] == "A retried webhook can double-charge before the refund is issued."


def test_parses_response_wrapped_in_code_fence():
    text = f"```json\n{json.dumps(_valid_batch_payload())}\n```"
    result = parse_faqs_response(text, expected_count=2)
    assert len(result) == 2


def test_reorders_entries_by_cluster_index_regardless_of_response_order():
    payload = list(reversed(_valid_batch_payload()))  # index 1 first, then 0
    result = parse_faqs_response(json.dumps(payload), expected_count=2)
    assert result[0]["question"] == _valid_faq()["question"]


def test_rejects_response_that_is_not_a_json_array():
    import pytest

    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(_valid_faq()), expected_count=1)


def test_rejects_wrong_entry_count():
    import pytest

    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(_valid_batch_payload()), expected_count=3)


def test_rejects_duplicate_cluster_index():
    import pytest

    payload = [{"cluster_index": 0, **_valid_faq()}, {"cluster_index": 0, **_valid_faq()}]
    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(payload), expected_count=2)


def test_rejects_out_of_range_cluster_index():
    import pytest

    payload = [{"cluster_index": 0, **_valid_faq()}, {"cluster_index": 5, **_valid_faq()}]
    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(payload), expected_count=2)


def test_rejects_entry_missing_question_or_answer():
    import pytest

    payload = [{"cluster_index": 0, **_valid_faq(question="")}]
    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(payload), expected_count=1)


def test_rejects_entry_with_non_list_resolution_steps():
    import pytest

    payload = [{"cluster_index": 0, **_valid_faq(resolution_steps="not a list")}]
    with pytest.raises(ValueError):
        parse_faqs_response(json.dumps(payload), expected_count=1)


def test_escalation_defaults_to_empty_string_when_absent():
    faq = _valid_faq()
    del faq["escalation"]
    result = parse_faqs_response(json.dumps([{"cluster_index": 0, **faq}]), expected_count=1)
    assert result[0]["escalation"] == ""


def test_draft_makes_exactly_one_gemini_call_for_the_whole_batch():
    client = _fake_client(json.dumps(_valid_batch_payload()))
    result = draft_faqs_for_clusters(ENTRIES, client=client)
    assert len(result) == 2
    assert result[0]["question"] == _valid_faq()["question"]
    assert client.models.generate_content.call_count == 1


def test_parsed_response_is_flagged_gemini_generated():
    result = parse_faqs_response(json.dumps(_valid_batch_payload()), expected_count=2)
    assert all(entry["gemini_generated"] is True for entry in result)


def test_template_fallback_is_flagged_not_gemini_generated():
    result = template_fallback(THEME_A, CLUSTER_A, TICKETS_A)
    assert result["gemini_generated"] is False


def test_draft_retries_once_then_falls_back_to_templates_for_every_cluster():
    client = _fake_client("not json at all")
    result = draft_faqs_for_clusters(ENTRIES, client=client, max_attempts=2)
    assert client.models.generate_content.call_count == 2
    assert result == [
        template_fallback(THEME_A, CLUSTER_A, TICKETS_A),
        template_fallback(THEME_B, CLUSTER_B, TICKETS_B),
    ]


def test_draft_falls_back_when_no_client_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = draft_faqs_for_clusters(ENTRIES, client=None)
    assert result == [
        template_fallback(THEME_A, CLUSTER_A, TICKETS_A),
        template_fallback(THEME_B, CLUSTER_B, TICKETS_B),
    ]


def test_draft_falls_back_when_client_construction_raises(monkeypatch):
    """A broken google-genai install (missing package, import-time crash from
    a native dependency, etc.) must degrade to the template, not 500 the
    whole /api/faqs/generate request."""
    import api._lib.faq_drafting as faq_drafting_module

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(
        faq_drafting_module,
        "_get_client",
        lambda: (_ for _ in ()).throw(ImportError("DLL load failed")),
    )
    result = draft_faqs_for_clusters(ENTRIES, client=None)
    assert result == [
        template_fallback(THEME_A, CLUSTER_A, TICKETS_A),
        template_fallback(THEME_B, CLUSTER_B, TICKETS_B),
    ]


def test_draft_handles_empty_entries_without_calling_gemini():
    client = _fake_client(json.dumps([]))
    result = draft_faqs_for_clusters([], client=client)
    assert result == []
    assert client.models.generate_content.call_count == 0


def test_template_fallback_is_grounded_in_real_ticket_resolutions():
    result = template_fallback(THEME_A, CLUSTER_A, TICKETS_A)
    assert TICKETS_A[0]["resolution"] in result["resolution_steps"]
    assert TICKETS_A[1]["resolution"] in result["resolution_steps"]
    assert result["escalation"] == ""


def test_template_fallback_question_is_not_the_banned_generic_phrasing():
    result = template_fallback(THEME_A, CLUSTER_A, TICKETS_A)
    assert "issues related to" not in result["question"].lower()


def test_template_fallback_deduplicates_identical_resolutions():
    tickets = [
        {"subject": "A", "description": "", "resolution": "Same fix applied"},
        {"subject": "B", "description": "", "resolution": "Same fix applied"},
    ]
    result = template_fallback(THEME_A, CLUSTER_A, tickets)
    assert result["resolution_steps"] == ["Same fix applied"]
