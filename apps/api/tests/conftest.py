"""Test setup: a dedicated Postgres database (reclaim_test), migrated with Alembic once per run
and reseeded before every test. Needs `docker compose up -d db` (see apps/api/README.md)."""

import os
import tempfile

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://reclaim:reclaim@localhost:5433/reclaim_test")
os.environ["WORKER_MODE"] = "external"  # tests drain the outbox explicitly
os.environ["ENABLE_DEV_ROUTES"] = "true"
os.environ["RATE_LIMITS_ENABLED"] = "false"  # enabled per test where needed
os.environ["SIMULATED_COURIER_SECONDS"] = "3600"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="reclaim-test-uploads-")
for var in ("AI_API_KEY", "ZAPIER_WEBHOOK_URL", "ZAPIER_URL_MATCH_HIGH_PRIORITY", "ZAPIER_URL_CLAIM_CREATED",
            "ZAPIER_WEBHOOK_SECRET", "PAYPAL_CLIENT_ID",
            "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID"):
    os.environ[var] = ""

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import config  # noqa: E402
from app.db.session import transaction  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import load_seed  # noqa: E402
from app.workers.outbox import drain  # noqa: E402

PW = "reclaim-demo"

assert config.settings.database_url.endswith("/reclaim_test"), "tests must never run against the dev database"


@pytest.fixture(scope="session", autouse=True)
def migrated():
    command.upgrade(Config(str(config.API_ROOT / "alembic.ini")), "head")


class DrainingClient(TestClient):
    """Runs the outbox worker after every request, so async jobs (matching, extraction,
    Zapier delivery) have finished before the test's next request."""

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        drain()
        return response


@pytest.fixture()
def client():
    with transaction():
        load_seed()
    with DrainingClient(app) as c:
        yield c


@pytest.fixture()
def login(client):
    def _login(email: str) -> TestClient:
        c = DrainingClient(app)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PW})
        assert r.status_code == 200, r.text
        return c

    return _login
