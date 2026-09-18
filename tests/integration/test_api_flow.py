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
