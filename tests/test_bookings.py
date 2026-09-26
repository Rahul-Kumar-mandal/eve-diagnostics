def test_create_booking_success(client, auth_headers, centre_and_test):
    headers = auth_headers()
    resp = client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["amount"] == 499.0  # derived from the test price server-side


def test_create_booking_invalid_test_404(client, auth_headers, centre_and_test):
    headers = auth_headers()
    resp = client.post(
        "/bookings/",
        json={
            "test_id": "nonexistent-test",
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_create_booking_mismatched_centre_400(client, auth_headers, centre_and_test):
    headers = auth_headers()
    other_centre = client.post("/centres/", json={"name": "Other Centre", "location": "Delhi"}, headers=headers).json()
    resp = client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": other_centre["id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_user_cannot_view_others_booking(client, auth_headers, centre_and_test):
    owner_headers = auth_headers(email="owner@example.com")
    booking = client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=owner_headers,
    ).json()

    stranger_headers = auth_headers(email="stranger@example.com")
    resp = client.get(f"/bookings/{booking['id']}", headers=stranger_headers)
    assert resp.status_code == 403


def test_get_nonexistent_booking_404(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/bookings/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_cancel_booking(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    ).json()

    resp = client.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # Cancelling again should conflict, not silently succeed.
    resp2 = client.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert resp2.status_code == 409


def test_list_bookings_only_returns_own(client, auth_headers, centre_and_test):
    headers_a = auth_headers(email="a2@example.com")
    headers_b = auth_headers(email="b2@example.com")

    client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers_a,
    )

    resp_b = client.get("/bookings/", headers=headers_b)
    assert resp_b.json()["total"] == 0

    resp_a = client.get("/bookings/", headers=headers_a)
    assert resp_a.json()["total"] == 1
