import os
import tempfile

import pytest


@pytest.fixture()
def _test_env():
    """Point the app at a throwaway SQLite file and make sure Gemini is never
    actually called during integration tests - draft_faq_for_cluster falls back
    to its deterministic template when GEMINI_API_KEY is unset.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    os.environ["TEST_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.pop("GEMINI_API_KEY", None)
    yield
    os.remove(db_path)


def _clear_api_modules():
    import sys

    for name in list(sys.modules):
        if name == "api" or name.startswith("api."):
            del sys.modules[name]


@pytest.fixture()
def client(_test_env):
    # api._lib.db resolves its engine from the environment at import time, so each test
    # needs a fresh import after TEST_DATABASE_URL is (re)pointed at its own throwaway file.
    _clear_api_modules()

    from fastapi.testclient import TestClient

    from api._lib.db import engine
    from api.index import app

    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()  # release the SQLite file handle before the temp file is removed
    _clear_api_modules()


@pytest.fixture()
def sample_csv_bytes():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "data", "sample_tickets.csv"), "rb") as f:
        return f.read()
