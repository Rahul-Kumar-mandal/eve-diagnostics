from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.services.payment_service import generate_provider_reference, simulate_payment_outcome

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/", response_model=schemas.PaymentOut, status_code=status.HTTP_201_CREATED)
def make_payment(
    payload: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Simulates initiating a payment for a booking against a mock gateway.

    Two modes, chosen by `async_confirmation`:
      * False (default): the mock gateway "responds" immediately, so we
        settle the payment and the booking in the same request. Simplest
        path, good enough for most flows.
      * True: mimics a real async gateway. The payment is created as
        PENDING and the booking is left PENDING; the final SUCCESS/FAILED
        status is only applied later, when the (simulated) provider calls
        POST /payments/webhook/ with this payment's `provider_reference`.
    """
    booking = db.query(models.Booking).filter(models.Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to pay for this booking")

    if booking.status != models.BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking is {booking.status.value}; only PENDING bookings can be paid for",
        )

    payment = models.Payment(
        booking_id=booking.id,
        provider_reference=generate_provider_reference(),
        amount=booking.amount,
        status=models.PaymentStatus.PENDING,
    )
    db.add(payment)

    if not payload.async_confirmation:
        outcome = simulate_payment_outcome(forced_result=payload.simulate_result)
        payment.status = outcome
        booking.status = (
            models.BookingStatus.CONFIRMED if outcome == models.PaymentStatus.SUCCESS
            else models.BookingStatus.FAILED
        )

    db.commit()
    db.refresh(payment)
    return payment


@router.post("/webhook/", response_model=schemas.MessageResponse)
def payment_webhook(
    payload: schemas.WebhookPayload,
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    """
    Receives asynchronous payment-status notifications from the (simulated)
    payment provider.

    Idempotency strategy (two layers, defence in depth):
      1. `event_id` uniqueness: every webhook delivery has a unique event_id.
         We try to record it in `webhook_events` under a UNIQUE constraint
         before doing anything else. If that insert fails because the
         event_id was already recorded, we know this exact delivery was
         already processed (e.g. the provider retried after a timeout) and
         we return success without touching any state again.
      2. Terminal-state check on the Payment: even if the provider sent a
         *different* event_id for what is logically the same status update,
         we never move a payment/booking out of a terminal state
         (SUCCESS/FAILED) once reached, so replays can't corrupt state.
    """
    if x_webhook_secret != settings.webhook_shared_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook credentials")

    # --- Layer 1: event-level idempotency ---
    # Record receipt of this event_id before doing anything else. The UNIQUE
    # constraint on event_id is what actually enforces idempotency: if this
    # exact delivery was already received (e.g. the provider retried after a
    # timeout), the insert fails and we stop immediately without touching
    # payment/booking state at all.
    event = models.WebhookEvent(event_id=payload.event_id, payload=payload.model_dump_json())
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return schemas.MessageResponse(message="Event already processed; no action taken")

    # --- Look up the payment this event refers to ---
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.provider_reference == payload.provider_reference)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown payment reference")

    # --- Layer 2: state-level idempotency ---
    if payment.status != models.PaymentStatus.PENDING:
        return schemas.MessageResponse(
            message=f"Payment already in terminal state {payment.status.value}; no action taken"
        )

    booking = db.query(models.Booking).filter(models.Booking.id == payment.booking_id).first()

    payment.status = payload.status
    if booking is not None:
        booking.status = (
            models.BookingStatus.CONFIRMED if payload.status == models.PaymentStatus.SUCCESS
            else models.BookingStatus.FAILED
        )

    db.commit()
    return schemas.MessageResponse(message="Webhook processed successfully")
