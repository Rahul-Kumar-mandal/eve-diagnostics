# EVE Healthcare — Diagnostic Bookings & Payments API

A backend service for browsing diagnostic centres/tests, booking a test, and
paying for it through a simulated (mock) payment gateway with an idempotent
webhook — built for the EVE Healthcare SDE Intern assignment.

**Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (SQLite fallback for zero-config
local runs), JWT auth (python-jose + passlib/bcrypt), Pytest.

---

## 1. Running it locally

### Option A — Docker (recommended, uses Postgres)

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`, backed by a Postgres
container. Interactive docs: `http://localhost:8000/docs`.

### Option B — Plain Python (uses SQLite, no external DB needed)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # defaults already work out of the box
python seed.py                   # optional: adds sample centres/tests
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for Swagger UI.

To point the plain-Python setup at Postgres instead of SQLite, set
`DATABASE_URL` in `.env` (see `.env.example`) to something like:

```
postgresql+psycopg2://eve:eve_password@localhost:5432/eve_healthcare
```

### Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

Tests run against an isolated in-memory SQLite database (see
`tests/conftest.py`) and don't touch your real database.

---

## 2. API Endpoints

All request/response bodies are JSON. Interactive, always-up-to-date docs are
served at `/docs` (Swagger) and `/redoc`.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | – | Create a new user |
| POST | `/auth/login` | – | Log in, get a JWT |

```bash
curl -X POST localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"StrongPass123","full_name":"Jane Doe"}'

curl -X POST localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"StrongPass123"}'
# => {"access_token": "<JWT>", "token_type": "bearer"}
```

Use the token on every protected endpoint:
`Authorization: Bearer <JWT>`

### Diagnostic Centres & Tests

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/centres/` | required | Create a diagnostic centre |
| GET | `/centres/` | – | List centres (paginated, `?location=` filter) |
| GET | `/centres/{centre_id}` | – | Get one centre with its tests |
| POST | `/centres/{centre_id}/tests/` | required | Add a test to a centre |
| GET | `/centres/{centre_id}/tests/` | – | List a centre's tests (paginated) |
| GET | `/tests/{test_id}` | – | Get a single test |

```bash
curl -X POST localhost:8000/centres/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name":"City Diagnostics","location":"Kolkata"}'

curl -X POST localhost:8000/centres/<centre_id>/tests/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Complete Blood Count","price":499.0}'

curl localhost:8000/centres/?location=Kolkata&limit=10&offset=0
```

### Bookings

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings/` | required | Book a test (status starts `PENDING`) |
| GET | `/bookings/` | required | List **your own** bookings (paginated) |
| GET | `/bookings/{booking_id}` | required | Get one of your bookings |
| POST | `/bookings/{booking_id}/cancel` | required | Cancel a booking |

```bash
curl -X POST localhost:8000/bookings/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"test_id":"<test_id>","centre_id":"<centre_id>","appointment_datetime":"2026-10-01T10:00:00Z"}'
```

The booking `amount` is always taken from the test's current price on the
server — the client cannot set or influence it.

### Payments

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | required | Simulate a payment for a booking |
| POST | `/payments/webhook/` | shared secret header | Receive an async payment-status update |

```bash
# Synchronous mock payment (default): settles immediately.
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id":"<booking_id>"}'
# random SUCCESS/FAILED outcome (80/20). Add "simulate_result":"SUCCESS"
# or "FAILED" to force a deterministic outcome for testing/demoing.

# Async mock payment: payment + booking stay PENDING until a webhook arrives.
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id":"<booking_id>","async_confirmation":true}'

# Simulated provider notifying the outcome later:
curl -X POST localhost:8000/payments/webhook/ \
  -H "X-Webhook-Secret: mock_provider_shared_secret" \
  -H "Content-Type: application/json" \
  -d '{"event_id":"evt-123","provider_reference":"mockpay_...","status":"SUCCESS"}'
```

**Why two payment modes?** A single mock endpoint that always settles
synchronously (as the assignment's minimum requirement) is enough to satisfy
the basic flow, but it never lets the webhook do anything meaningful. Adding
an opt-in `async_confirmation` mode lets both integration patterns — a
gateway that responds inline vs. one that confirms later via webhook — be
exercised and tested end-to-end, which is closer to how real payment
gateways (Stripe, Razorpay, etc.) actually behave.

---

## 3. Database / Schema Design

```
User
 ├─ id (PK, uuid string), email (unique), hashed_password, full_name,
 │  is_active, created_at

DiagnosticCentre
 ├─ id (PK), name, location, created_at

DiagnosticTest
 ├─ id (PK), centre_id (FK -> DiagnosticCentre), name, price, created_at

Booking
 ├─ id (PK), user_id (FK -> User), test_id (FK -> DiagnosticTest),
 │  centre_id (FK -> DiagnosticCentre), appointment_datetime, amount,
 │  status (PENDING | CONFIRMED | FAILED | CANCELLED), created_at, updated_at

Payment
 ├─ id (PK), booking_id (FK -> Booking),
 │  provider_reference (unique — the gateway's id for this payment attempt),
 │  amount, status (PENDING | SUCCESS | FAILED), created_at, updated_at

WebhookEvent
 ├─ id (PK), event_id (unique — the idempotency key for webhook delivery),
 │  payload (raw JSON, for audit/debugging), created_at
```

Design notes:

- **`centre_id` is duplicated on `Booking`** (it's derivable from
  `test.centre_id`) so a booking's centre stays correct even if a test is
  ever moved between centres later, and so booking queries don't need an
  extra join back through `DiagnosticTest`.
- **`amount` is stored on `Booking` and `Payment`, not just referenced from
  `DiagnosticTest.price`**, because test prices can change over time —
  a booking must remain a fixed record of what was actually charged.
- **A `Booking` can have more than one `Payment`** (one row per payment
  *attempt*): if a payment fails, the booking moves to `FAILED`, and (in a
  fuller implementation) a user could retry, creating a second `Payment` row
  for the same booking. This preserves a full audit trail instead of
  overwriting payment history.
- **`WebhookEvent` is the idempotency ledger.** `event_id` has a UNIQUE
  constraint; the webhook handler always tries to insert a row there first.
  If that insert fails (duplicate), we know this exact delivery was already
  handled and stop before touching any other state — see the "Idempotency"
  section below.
- IDs are UUID strings rather than auto-increment integers, so they don't
  leak sequence/volume information and are safe to hand out in URLs.

---

## 4. Idempotency & Edge Cases

- **Duplicate webhook events** (same `event_id` sent twice): the second
  delivery hits the `UNIQUE` constraint on `WebhookEvent.event_id`, so the
  insert fails, we roll back, and return `200` with an "already processed"
  message — no state is touched a second time. Tested in
  `test_webhook_is_idempotent_on_duplicate_event_id`.
- **Late/duplicate webhook with a *different* `event_id`** for a payment
  that's already `SUCCESS`/`FAILED` (a second line of defence, in case a
  provider ever re-sends a logically-duplicate event under a new id): the
  handler checks the payment's current status and refuses to move it out of
  a terminal state. Tested in
  `test_webhook_does_not_flip_already_terminal_payment`.
- **Invalid / forged webhook calls**: rejected with `401` unless the caller
  sends the correct `X-Webhook-Secret` header (`test_webhook_rejects_invalid_secret`).
- **Unknown `provider_reference`**: `404` (`test_webhook_unknown_provider_reference_404`).
- **Invalid booking ID** on `GET`, `cancel`, or `POST /payments/`: `404`.
- **Paying for/cancelling someone else's booking**: `403`
  (`test_cannot_pay_for_others_booking`, `test_user_cannot_view_others_booking`).
- **Double payment / paying for a non-`PENDING` booking** (already
  `CONFIRMED`, `FAILED`, or `CANCELLED`): `409 Conflict`, not a silent
  no-op or duplicate charge (`test_cannot_double_pay_a_confirmed_booking`,
  `test_cannot_pay_for_cancelled_booking`).
- **Cancelling an already-cancelled/failed booking**: `409 Conflict`.
- **Mismatched `test_id`/`centre_id`** on booking creation (a test that
  doesn't belong to the given centre): `400 Bad Request`.
- **Price/amount is never trusted from the client** — always derived
  server-side from the test's current price at booking time.
- **Basic request validation** throughout via Pydantic (e.g. password
  minimum length, positive prices, required fields) — invalid payloads get
  `422` with a field-level error list.

---

## 5. Assumptions

- Any authenticated user can register a diagnostic centre/test. There's no
  separate "admin" or "centre owner" role in this assignment's scope; in a
  real product, centre/test management would be restricted to a staff role.
- Reading centres/tests is public (no auth) since it's a browsing/catalog
  experience; booking and payments require auth.
- The mock payment gateway has no real external dependency — the "provider"
  is entirely simulated inside this service (`app/services/payment_service.py`),
  with a configurable random success rate and an optional forced outcome for
  deterministic testing.
- A booking's `amount` is fixed at booking time from the test's price at
  that moment (not re-derived at payment time), matching how real bookings
  lock in a price.
- The webhook is authenticated with a simple shared secret header rather
  than a full HMAC-signature scheme, to keep the assignment's scope
  reasonable — see "What I'd improve" below.

---

## 6. What I'd improve with more time

- **HMAC-signed webhooks** instead of a static shared secret, with a replay
  window check on the timestamp, for a more realistic provider integration.
- **Alembic migrations** instead of `Base.metadata.create_all()`, so schema
  changes are versioned and reproducible.
- **A proper role system** (patient vs. centre-admin vs. platform-admin) so
  centre/test management isn't open to every signed-up user.
- **Background processing** for payments/webhooks via Celery + Redis, so a
  slow/retrying provider call can't block the request thread, plus retry
  handling with backoff for webhook delivery failures on our side.
- **Rate limiting** on `/auth/login` and `/payments/webhook/` to blunt
  brute-force and abuse.
- **Structured (JSON) logging** with request IDs for tracing a booking
  through create → pay → webhook.
- **Refresh tokens** and token revocation, rather than a single long-lived
  access token.
- **Optimistic locking / row-level locking** on `Booking`/`Payment` updates
  to guard against race conditions if two requests hit the same booking at
  the same instant (currently only the application-level status checks in
  each request protect against double-processing).
- More exhaustive test coverage around pagination edge cases and centre/test
  update & delete endpoints (currently only create/read are implemented for
  the catalog, since the assignment emphasizes bookings/payments).

---

## 7. Project Structure

```
app/
  main.py              FastAPI app, router registration, error handlers
  config.py            Environment-driven settings
  database.py          SQLAlchemy engine/session/Base
  models.py            ORM models (User, DiagnosticCentre, DiagnosticTest,
                        Booking, Payment, WebhookEvent)
  schemas.py           Pydantic request/response models
  auth.py              Password hashing + JWT creation/verification
  deps.py              get_current_user dependency
  routers/
    auth.py            /auth/signup, /auth/login
    centres.py         /centres/, /centres/{id}/tests/, /tests/{id}
    bookings.py        /bookings/
    payments.py        /payments/, /payments/webhook/
  services/
    payment_service.py Mock payment-gateway simulation logic
tests/                 Pytest suite (auth, centres, bookings, payments/webhook)
seed.py                Optional sample-data seeding script
Dockerfile / docker-compose.yml
requirements.txt
.env.example
```
