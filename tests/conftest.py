import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # keep the same in-memory DB across connections
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def _reset_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    """Signs up and logs in a fresh user, returning Authorization headers."""

    def _make(email="patient@example.com", password="StrongPass123", full_name="Test Patient"):
        client.post(
            "/auth/signup",
            json={"email": email, "password": password, "full_name": full_name},
        )
        resp = client.post("/auth/login", json={"email": email, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def centre_and_test(client, auth_headers):
    """Creates a diagnostic centre with one test, returns their IDs."""
    headers = auth_headers()
    centre_resp = client.post(
        "/centres/", json={"name": "City Diagnostics", "location": "Kolkata"}, headers=headers
    )
    centre_id = centre_resp.json()["id"]

    test_resp = client.post(
        f"/centres/{centre_id}/tests/",
        json={"name": "Complete Blood Count", "price": 499.0},
        headers=headers,
    )
    test_id = test_resp.json()["id"]
    return {"centre_id": centre_id, "test_id": test_id}
