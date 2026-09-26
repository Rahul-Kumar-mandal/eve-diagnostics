import random
import uuid

from app.models import PaymentStatus

# Probability that a simulated payment succeeds when no explicit outcome is
# requested. Kept as a module constant so tests can monkeypatch it if needed.
SUCCESS_PROBABILITY = 0.8


def generate_provider_reference() -> str:
    """A unique reference id, as if issued by an external payment gateway."""
    return f"mockpay_{uuid.uuid4().hex}"


def simulate_payment_outcome(forced_result: PaymentStatus | None = None) -> PaymentStatus:
    """
    Simulates a call to a real payment gateway.

    If `forced_result` is provided (used by tests/demos to get deterministic
    behaviour) it is returned as-is. Otherwise the outcome is randomized to
    mimic real-world payment success/failure rates.
    """
    if forced_result is not None:
        return forced_result

    return PaymentStatus.SUCCESS if random.random() < SUCCESS_PROBABILITY else PaymentStatus.FAILED
