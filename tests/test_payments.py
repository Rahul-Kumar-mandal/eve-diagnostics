from app.config import settings

WEBHOOK_HEADERS = {"X-Webhook-Secret": settings.webhook_shared_secret}


def _create_booking(client, headers, centre_and_test):
    return client.post(
        "/bookings/",
        json={
            "test_id": centre_and_test["test_id"],
            "centre_id": centre_and_test["centre_id"],
            "appointment_datetime": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    ).json()


def test_synchronous_payment_success_confirms_booking(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)

    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate_result": "SUCCESS"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_after["status"] == "CONFIRMED"


def test_synchronous_payment_failure_fails_booking(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)

    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate_result": "FAILED"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "FAILED"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_after["status"] == "FAILED"


def test_cannot_pay_for_nonexistent_booking(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/payments/", json={"booking_id": "no-such-booking"}, headers=headers)
    assert resp.status_code == 404


def test_cannot_pay_for_others_booking(client, auth_headers, centre_and_test):
    owner_headers = auth_headers(email="owner2@example.com")
    booking = _create_booking(client, owner_headers, centre_and_test)

    stranger_headers = auth_headers(email="stranger2@example.com")
    resp = client.post("/payments/", json={"booking_id": booking["id"]}, headers=stranger_headers)
    assert resp.status_code == 403


def test_cannot_double_pay_a_confirmed_booking(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)

    client.post("/payments/", json={"booking_id": booking["id"], "simulate_result": "SUCCESS"}, headers=headers)
    resp = client.post("/payments/", json={"booking_id": booking["id"], "simulate_result": "SUCCESS"}, headers=headers)
    assert resp.status_code == 409


def test_cannot_pay_for_cancelled_booking(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)
    client.post(f"/bookings/{booking['id']}/cancel", headers=headers)

    resp = client.post("/payments/", json={"booking_id": booking["id"]}, headers=headers)
    assert resp.status_code == 409


def test_async_payment_stays_pending_until_webhook(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)

    payment = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "async_confirmation": True},
        headers=headers,
    ).json()
    assert payment["status"] == "PENDING"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_after["status"] == "PENDING"

    # Now the (simulated) provider notifies success via webhook.
    webhook_resp = client.post(
        "/payments/webhook/",
        json={
            "event_id": "evt-1",
            "provider_reference": payment["provider_reference"],
            "status": "SUCCESS",
        },
        headers=WEBHOOK_HEADERS,
    )
    assert webhook_resp.status_code == 200

    booking_final = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_final["status"] == "CONFIRMED"


def test_webhook_is_idempotent_on_duplicate_event_id(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)
    payment = client.post(
        "/payments/", json={"booking_id": booking["id"], "async_confirmation": True}, headers=headers
    ).json()

    webhook_body = {
        "event_id": "evt-dup",
        "provider_reference": payment["provider_reference"],
        "status": "SUCCESS",
    }

    first = client.post("/payments/webhook/", json=webhook_body, headers=WEBHOOK_HEADERS)
    second = client.post("/payments/webhook/", json=webhook_body, headers=WEBHOOK_HEADERS)

    assert first.status_code == 200
    assert second.status_code == 200
    assert "already processed" in second.json()["message"].lower()

    # Booking must have transitioned exactly once, ending in a consistent state.
    booking_final = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_final["status"] == "CONFIRMED"


def test_webhook_does_not_flip_already_terminal_payment(client, auth_headers, centre_and_test):
    """A different event_id but referring to an already-settled payment must not corrupt state."""
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)
    payment = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate_result": "SUCCESS"},
        headers=headers,
    ).json()  # settles synchronously -> booking CONFIRMED

    # A stray/late webhook (different event_id) tries to mark it FAILED.
    resp = client.post(
        "/payments/webhook/",
        json={
            "event_id": "evt-late-and-wrong",
            "provider_reference": payment["provider_reference"],
            "status": "FAILED",
        },
        headers=WEBHOOK_HEADERS,
    )
    assert resp.status_code == 200
    assert "terminal state" in resp.json()["message"].lower()

    booking_final = client.get(f"/bookings/{booking['id']}", headers=headers).json()
    assert booking_final["status"] == "CONFIRMED"  # unchanged


def test_webhook_rejects_invalid_secret(client, auth_headers, centre_and_test):
    headers = auth_headers()
    booking = _create_booking(client, headers, centre_and_test)
    payment = client.post(
        "/payments/", json={"booking_id": booking["id"], "async_confirmation": True}, headers=headers
    ).json()

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-x", "provider_reference": payment["provider_reference"], "status": "SUCCESS"},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_webhook_unknown_provider_reference_404(client):
    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-y", "provider_reference": "mockpay_does_not_exist", "status": "SUCCESS"},
        headers=WEBHOOK_HEADERS,
    )
    assert resp.status_code == 404
