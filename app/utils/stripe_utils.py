import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_checkout_session(upload_id: str, email: str, amount_cents: int, token: str | None = None):
    success_url = f"{os.getenv('PUBLIC_BASE_URL')}/success?upload_id={upload_id}"
    cancel_url = f"{os.getenv('PUBLIC_BASE_URL')}/?cancel=1"

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "MailSized Compression"},
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        metadata={
            "upload_id": upload_id,
            "token_used": token or ""
        },
        customer_email=email,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    print(f"✅ Stripe session created: {session.id} for ${amount_cents / 100:.2f}")
    return session
