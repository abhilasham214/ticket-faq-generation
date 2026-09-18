import os

import pytest


@pytest.fixture()
def client():
    """FastAPI TestClient against the real app. No database - each request is
    self-contained, so there's no state to isolate between tests beyond
    making sure Gemini and Vercel KV are never actually called (drafting
    falls back to its deterministic template when GEMINI_API_KEY is unset;
    category/ticket stores fall back to their in-request defaults when
    KV_REST_API_URL/KV_REST_API_TOKEN are unset).
    """
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("KV_REST_API_URL", None)
    os.environ.pop("KV_REST_API_TOKEN", None)

    from fastapi.testclient import TestClient

    from api.index import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sample_csv_bytes():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "data", "sample_tickets.csv"), "rb") as f:
        return f.read()


@pytest.fixture()
def new_domain_csv_bytes():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "data", "sample_tickets_new_domain.csv"), "rb") as f:
        return f.read()
