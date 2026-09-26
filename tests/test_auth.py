def test_signup_success(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "a@example.com", "password": "StrongPass123", "full_name": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "hashed_password" not in body


def test_signup_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "StrongPass123", "full_name": "Dup"}
    client.post("/auth/signup", json=payload)
    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 409


def test_signup_weak_password_rejected(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "b@example.com", "password": "short", "full_name": "Bob"},
    )
    assert resp.status_code == 422


def test_login_success_returns_jwt(client):
    client.post(
        "/auth/signup",
        json={"email": "c@example.com", "password": "StrongPass123", "full_name": "Carl"},
    )
    resp = client.post("/auth/login", json={"email": "c@example.com", "password": "StrongPass123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


def test_login_wrong_password_rejected(client):
    client.post(
        "/auth/signup",
        json={"email": "d@example.com", "password": "StrongPass123", "full_name": "Dana"},
    )
    resp = client.post("/auth/login", json={"email": "d@example.com", "password": "WrongPass123"})
    assert resp.status_code == 401


def test_protected_endpoint_requires_token(client):
    resp = client.get("/bookings/")
    assert resp.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client):
    resp = client.get("/bookings/", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
