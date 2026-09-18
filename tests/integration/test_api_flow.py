def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_generate_faqs_from_sample_csv_produces_five_clean_themes(client, sample_csv_bytes):
    """End-to-end check against the real 20-ticket sample dataset: exactly the
    5 true themes (login, billing, API, data export/import, email), each
    with all 4 of its tickets, no theme mixing unrelated tickets together."""
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("sample_tickets.csv", sample_csv_bytes, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()

    assert body["total_tickets"] == 20
    assert len(body["clusters"]) == 5
    assert sum(c["ticket_count"] for c in body["clusters"]) == 20
    assert all(c["ticket_count"] == 4 for c in body["clusters"])

    themes = {c["theme"] for c in body["clusters"]}
    assert themes == {
        "API Authentication & Rate Limit Issues",
        "Data Export & Import Issues",
        "Password Reset & Account Recovery",
        "Email & Notification Delivery Issues",
        "Billing & Duplicate Charge Issues",
    }

    for cluster in body["clusters"]:
        assert cluster["faq"]["question"]
        assert cluster["faq"]["answer"]
        assert isinstance(cluster["faq"]["resolution_steps"], list)
        assert "/" not in cluster["theme"]
        # No GEMINI_API_KEY in this test env - every curated cluster's theme
        # and FAQ must be flagged as the deterministic fallback, not silently
        # look identical to a real Gemini-drafted result.
        assert cluster["is_new_domain"] is False
        assert cluster["ai_named"] is False
        assert cluster["faq"]["gemini_generated"] is False


def test_uncategorized_theme_is_flagged_as_new_domain(client, new_domain_csv_bytes):
    """A cluster that matches none of the 5 curated domains must be flagged
    is_new_domain=True regardless of whether Gemini successfully named it -
    that's what lets the UI distinguish "new theme, Gemini named it" from
    "new theme, Gemini was unavailable" instead of the latter looking like
    an ordinary curated match."""
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("new_domain.csv", new_domain_csv_bytes, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()

    new_domain_clusters = [c for c in body["clusters"] if c["is_new_domain"]]
    assert len(new_domain_clusters) == 1
    assert new_domain_clusters[0]["ticket_count"] == 4
    # No GEMINI_API_KEY in this test env, so it can't have been AI-named.
    assert new_domain_clusters[0]["ai_named"] is False

    curated_clusters = [c for c in body["clusters"] if not c["is_new_domain"]]
    assert len(curated_clusters) == 2
    assert {c["theme"] for c in curated_clusters} == {
        "Password Reset & Account Recovery",
        "Billing & Duplicate Charge Issues",
    }


def test_generate_from_sample_endpoint_matches_uploading_the_same_csv(client):
    """POST /api/faqs/generate/sample needs no file - it should produce the
    same 5-theme, 20-ticket result as uploading data/sample_tickets.csv
    directly, since that's the bundled fallback ticket_store.py seeds from."""
    res = client.post("/api/faqs/generate/sample")
    assert res.status_code == 200
    body = res.json()

    assert body["total_tickets"] == 20
    assert len(body["clusters"]) == 5
    assert sum(c["ticket_count"] for c in body["clusters"]) == 20


def test_latest_endpoint_falls_back_to_seeded_sample_when_nothing_generated_yet(client):
    """With no KV configured (the test client fixture strips those env vars)
    and nothing generated yet this test run, GET /api/faqs/latest should
    still return the seeded sample set rather than an empty/error response -
    "the app never opens empty" contract."""
    res = client.get("/api/faqs/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["total_tickets"] == 20
    assert len(body["clusters"]) == 5


def test_every_cluster_traces_back_to_its_source_tickets(client, sample_csv_bytes):
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("sample_tickets.csv", sample_csv_bytes, "text/csv")},
    )
    body = res.json()

    for cluster in body["clusters"]:
        assert cluster["ticket_ids"] == [t["ticket_id"] for t in cluster["tickets"]]
        for ticket in cluster["tickets"]:
            assert ticket["ticket_id"].startswith("TCK-")
            assert ticket["title"]
            assert ticket["resolution"]


def test_generate_with_minimal_but_sufficient_csv_still_returns_a_cluster(client):
    csv_bytes = (
        b"id,subject,resolution\n"
        b"T1,Cannot log in,Cleared session cookie\n"
        b"T2,Billed twice,Refunded the duplicate charge\n"
        b"T3,API key expired,Issued a new API key\n"
    )
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("small.csv", csv_bytes, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_tickets"] == 3
    assert len(body["clusters"]) >= 1


def test_generate_rejects_non_csv_file(client):
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("tickets.txt", b"not a csv", "text/plain")},
    )
    assert res.status_code == 400


def test_generate_rejects_csv_missing_resolution_column(client):
    bad_csv = b"id,subject\nT1,A\nT2,B\nT3,C\n"
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("tickets.csv", bad_csv, "text/csv")},
    )
    assert res.status_code == 400
    assert "resolution" in res.json()["detail"]


def test_generate_rejects_csv_missing_id_column(client):
    bad_csv = b"subject,resolution\nA,B\nC,D\nE,F\n"
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("tickets.csv", bad_csv, "text/csv")},
    )
    assert res.status_code == 400
    assert "id" in res.json()["detail"]


def test_generate_rejects_too_few_tickets(client):
    small_csv = b"id,subject,resolution\nT1,A,B\nT2,C,D\n"
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("small.csv", small_csv, "text/csv")},
    )
    assert res.status_code == 400
    assert res.status_code != 500


def test_ask_about_ticket_returns_503_when_gemini_not_configured(client):
    """The client fixture strips GEMINI_API_KEY, so this always hits the
    "investigation unavailable" path - there's no deterministic fallback for
    an open-ended question, so it must 503 rather than fake a 200 answer."""
    res = client.post(
        "/api/tickets/ask",
        json={
            "title": "API returns 429 errors during normal usage",
            "description": "",
            "resolution": "Fixed the rate limiter to key on (api_key, endpoint).",
            "question": "What was the root cause?",
        },
    )
    assert res.status_code == 503


def test_ask_about_ticket_rejects_empty_question(client):
    res = client.post(
        "/api/tickets/ask",
        json={
            "title": "API returns 429 errors during normal usage",
            "description": "",
            "resolution": "Fixed the rate limiter.",
            "question": "   ",
        },
    )
    assert res.status_code == 400
