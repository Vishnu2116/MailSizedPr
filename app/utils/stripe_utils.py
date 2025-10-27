# app/utils/stripe_utils.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_checkout_session(upload_id: str, email: str, amount_cents: int, token_obj=None):
    BASE = os.getenv("PUBLIC_BASE_URL", "https://mailsized.com").rstrip("/")
    if not BASE:
        raise RuntimeError("PUBLIC_BASE_URL is not set")

    # ✅ include upload_id so the front-end knows what to resume
    success_url = f"{BASE}/?paid=1&upload_id={upload_id}"
    cancel_url  = f"{BASE}/?cancel=1&upload_id={upload_id}"

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
    # Stripe minimum charge guard (USD 50¢)
    if 0 < discounted_amount < 50:
        discounted_amount = 50

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
    return session
