import os

os.environ.setdefault("STUB_PROCESSING_SECONDS", "0")
os.environ.setdefault("STUB_COURIER_SECONDS", "3600")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PW = "reclaim-demo"


@pytest.fixture()
def client():
    with TestClient(app) as c:  # lifespan reloads the seed for every test
        yield c


@pytest.fixture()
def login(client):
    def _login(email: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PW})
        assert r.status_code == 200, r.text
        return c

    return _login
