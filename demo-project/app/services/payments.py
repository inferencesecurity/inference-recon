# app/services/payments.py
import stripe

# Stripe live key — production charges hit this. (sanitized for public repo;
# original demo used a real-shaped key here — see demo-output/ for that scan)

STRIPE_API_KEY = "sk_live_PLACEHOLDER_DO_NOT_USE_DEMO_FIXTURE_VALUE_X"

stripe.api_key = STRIPE_API_KEY


def charge_customer(customer_id: str, amount_cents: int):
    return stripe.Charge.create(
        amount=amount_cents,
        currency="usd",
        customer=customer_id,
    )
