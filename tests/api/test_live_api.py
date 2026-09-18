"""Black-box smoke tests against a *running* instance (e.g. `vercel dev` or the
deployed Vercel URL). Skipped by default - set BASE_URL to run them:

    BASE_URL=http://localhost:3000 pytest tests/api

These hit the real HTTP contract with no internal mocking. The Postman collection
under postman/ covers the full functional/negative/edge matrix; this file is a
couple of CI-friendly spot checks for environments where Newman isn't wired in.
"""

import os
import pathlib

import httpx
import pytest

BASE_URL = os.environ.get("BASE_URL")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="BASE_URL not set - skipping live API smoke tests")

SAMPLE_CSV = pathlib.Path(__file__).resolve().parents[2] / "data" / "sample_tickets.csv"


def test_health_endpoint_is_reachable():
    res = httpx.get(f"{BASE_URL}/api/health", timeout=30)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_full_round_trip_against_live_instance():
    with open(SAMPLE_CSV, "rb") as f:
        generate = httpx.post(
            f"{BASE_URL}/api/faqs/generate",
            files={"file": ("sample_tickets.csv", f, "text/csv")},
            timeout=60,
        )
    assert generate.status_code == 200
    body = generate.json()
    assert len(body["clusters"]) == 5
    assert body["total_tickets"] == 20
    for cluster in body["clusters"]:
        assert cluster["theme"]
        assert cluster["faq"]["question"]
        assert cluster["faq"]["answer"]
        assert cluster["tickets"]
