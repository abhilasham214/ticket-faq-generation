def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_generate_faqs_from_csv(client, sample_csv_bytes):
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("sample_tickets.csv", sample_csv_bytes, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()

    assert 3 <= len(body["clusters"]) <= 5
    assert body["total_tickets"] == 20
    assert sum(c["ticket_count"] for c in body["clusters"]) == 20
    for cluster in body["clusters"]:
        assert cluster["faq"]["question"]
        assert cluster["faq"]["answer"]


def test_generate_with_small_csv_still_returns_at_least_one_cluster(client):
    small_csv = (
        b"subject,description,resolution\n"
        b"Cannot log in,Password rejected after reset,Cleared stale session cookie\n"
        b"Billed twice,Duplicate charge on invoice,Refunded the duplicate charge\n"
    )
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("small.csv", small_csv, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_tickets"] == 2
    assert len(body["clusters"]) >= 1


def test_generate_rejects_non_csv_file(client):
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("tickets.txt", b"not a csv", "text/plain")},
    )
    assert res.status_code == 400


def test_generate_rejects_csv_missing_required_columns(client):
    bad_csv = b"subject,description\nA,B\n"
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("tickets.csv", bad_csv, "text/csv")},
    )
    assert res.status_code == 400
    assert "resolution" in res.json()["detail"]


def test_generate_rejects_csv_with_no_usable_rows(client):
    empty_csv = b"subject,description,resolution\n"
    res = client.post(
        "/api/faqs/generate",
        files={"file": ("empty.csv", empty_csv, "text/csv")},
    )
    assert res.status_code == 400
