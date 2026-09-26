from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import BookingStatus, PaymentStatus


# ---------- Auth ----------

class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Centres & Tests ----------

class DiagnosticTestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)


class DiagnosticTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    centre_id: str
    name: str
    price: float


class DiagnosticCentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)


class DiagnosticCentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    location: str
    tests: List[DiagnosticTestOut] = []


class Paginated(BaseModel):
    total: int
    limit: int
    offset: int


class PaginatedCentres(Paginated):
    items: List[DiagnosticCentreOut]


class PaginatedTests(Paginated):
    items: List[DiagnosticTestOut]


# ---------- Bookings ----------

class BookingCreate(BaseModel):
    test_id: str
    centre_id: str
    appointment_datetime: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    test_id: str
    centre_id: str
    appointment_datetime: datetime
    amount: float
    status: BookingStatus
    created_at: datetime
    updated_at: datetime


class PaginatedBookings(Paginated):
    items: List[BookingOut]


# ---------- Payments ----------

class PaymentCreate(BaseModel):
    booking_id: str
    # Optional override used only for testing/demoing deterministic outcomes.
    # In a real gateway integration this would never be client-controlled.
    simulate_result: Optional[PaymentStatus] = None
    # If True, the payment is left PENDING and only settled later by a call
    # to /payments/webhook/ - mimicking a real async gateway. If False
    # (default), the mock settles the payment immediately, which is enough
    # to satisfy most flows and is simpler to test end-to-end.
    async_confirmation: bool = False


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    provider_reference: str
    amount: float
    status: PaymentStatus
    created_at: datetime


class WebhookPayload(BaseModel):
    event_id: str = Field(description="Unique ID of this webhook event, used for idempotency")
    provider_reference: str = Field(description="The payment's provider_reference")
    status: PaymentStatus


class MessageResponse(BaseModel):
    message: str
