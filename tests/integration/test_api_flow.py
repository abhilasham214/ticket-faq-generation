def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_full_upload_generate_fetch_flow(client, sample_csv_bytes):
    upload_res = client.post(
        "/api/tickets/upload",
        files={"file": ("sample_tickets.csv", sample_csv_bytes, "text/csv")},
    )
    assert upload_res.status_code == 200
    upload_body = upload_res.json()
    assert upload_body["ticket_count"] == 20

    generate_res = client.post("/api/faqs/generate")
    assert generate_res.status_code == 200
    generate_body = generate_res.json()

    assert 3 <= len(generate_body["clusters"]) <= 5
    assert generate_body["total_tickets"] == 20
    assert sum(c["ticket_count"] for c in generate_body["clusters"]) == 20
    for cluster in generate_body["clusters"]:
        assert cluster["faq"]["question"]
        assert cluster["faq"]["answer"]

    get_res = client.get("/api/faqs")
    assert get_res.status_code == 200
    get_body = get_res.json()
    assert get_body["total_tickets"] == 20
    assert len(get_body["clusters"]) == len(generate_body["clusters"])


def test_reupload_replaces_previous_batch(client, sample_csv_bytes):
    client.post(
        "/api/tickets/upload",
        files={"file": ("sample_tickets.csv", sample_csv_bytes, "text/csv")},
    )
    client.post("/api/faqs/generate")

    small_csv = b"subject,description,resolution\nA,B,C\nD,E,F\n"
    second_upload = client.post(
        "/api/tickets/upload",
        files={"file": ("small.csv", small_csv, "text/csv")},
    )
    assert second_upload.status_code == 200
    assert second_upload.json()["ticket_count"] == 2

    faqs_res = client.get("/api/faqs")
    assert faqs_res.json()["total_tickets"] == 2
    assert faqs_res.json()["clusters"] == []


def test_upload_rejects_non_csv_file(client):
    res = client.post(
        "/api/tickets/upload",
        files={"file": ("tickets.txt", b"not a csv", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_rejects_csv_missing_required_columns(client):
    bad_csv = b"subject,description\nA,B\n"
    res = client.post(
        "/api/tickets/upload",
        files={"file": ("tickets.csv", bad_csv, "text/csv")},
    )
    assert res.status_code == 400
    assert "resolution" in res.json()["detail"]


def test_generate_with_no_tickets_returns_handled_error(client):
    res = client.post("/api/faqs/generate")
    assert res.status_code == 400
    assert res.status_code != 500
