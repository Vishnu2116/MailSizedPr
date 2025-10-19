# app/utils/stripe_utils.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def create_checkout_session(upload_id: str, email: str, amount_cents: int, token_obj=None):
    """Create a Stripe Checkout Session with optional discount."""
    success_url = f"{os.getenv('PUBLIC_BASE_URL')}/success?upload_id={upload_id}"
    cancel_url = f"{os.getenv('PUBLIC_BASE_URL')}/?cancel=1"

    # ───── Apply token discount if available ─────
    discount_percent = 0
    token_code = ""
    if token_obj:
        try:
            discount_percent = int(token_obj.discount_percent or 0)
            token_code = token_obj.code
        except Exception:
            discount_percent = 0

    discounted_amount = int(amount_cents * (1 - discount_percent / 100))
    if discounted_amount < 0:
        discounted_amount = 0

    print(f"🎟️ Discount applied: {discount_percent}% → Final charge ${discounted_amount / 100:.2f}")

    # ───── Create Stripe Checkout Session ─────
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "MailSized Compression"},
                "unit_amount": discounted_amount,
            },
            "quantity": 1,
        }],
        metadata={
            "upload_id": upload_id,
            "token_used": token_code,
            "discount_percent": discount_percent,
        },
        customer_email=email,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    print(f"✅ Stripe session created: {session.id} for ${discounted_amount / 100:.2f}")
    return session
