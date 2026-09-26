def test_create_and_list_centre(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/centres/", json={"name": "Apollo Diagnostics", "location": "Mumbai"}, headers=headers)
    assert resp.status_code == 201

    resp = client.get("/centres/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Apollo Diagnostics"


def test_create_centre_requires_auth(client):
    resp = client.post("/centres/", json={"name": "No Auth Centre", "location": "Delhi"})
    assert resp.status_code == 401


def test_add_test_to_centre(client, auth_headers):
    headers = auth_headers()
    centre_resp = client.post("/centres/", json={"name": "Metro Labs", "location": "Pune"}, headers=headers)
    centre_id = centre_resp.json()["id"]

    resp = client.post(
        f"/centres/{centre_id}/tests/",
        json={"name": "Lipid Profile", "price": 799.0},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["price"] == 799.0

    centre_detail = client.get(f"/centres/{centre_id}").json()
    assert len(centre_detail["tests"]) == 1


def test_add_test_to_nonexistent_centre_404(client, auth_headers):
    headers = auth_headers()
    resp = client.post(
        "/centres/does-not-exist/tests/",
        json={"name": "X-Ray", "price": 300.0},
        headers=headers,
    )
    assert resp.status_code == 404


def test_negative_price_rejected(client, auth_headers):
    headers = auth_headers()
    centre_id = client.post("/centres/", json={"name": "Test Centre", "location": "Kolkata"}, headers=headers).json()["id"]
    resp = client.post(
        f"/centres/{centre_id}/tests/",
        json={"name": "Bad Test", "price": -50.0},
        headers=headers,
    )
    assert resp.status_code == 422


def test_get_nonexistent_centre_404(client):
    resp = client.get("/centres/no-such-id")
    assert resp.status_code == 404


def test_pagination_params(client, auth_headers):
    headers = auth_headers()
    for i in range(3):
        client.post("/centres/", json={"name": f"Centre {i}", "location": "Kolkata"}, headers=headers)

    resp = client.get("/centres/?limit=2&offset=0")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
