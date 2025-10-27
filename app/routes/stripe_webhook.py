# app/routes/stripe_webhook.py
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from app.db import SessionLocal
from app import repo
from app.utils.redis_utils import enqueue_job

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """
    Handles Stripe events:
      - On checkout.session.completed:
          * Ensure a job exists or create fallback
          * Update price_cents and status
          * Enqueue to Redis for worker processing
          * Consume token if present
    """
    payload = await request.body()

    # ─────────────── Verify Signature ───────────────
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=endpoint_secret,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature error: {str(e)}")

    # ─────────────── Handle Checkout Success ───────────────
    if event.get("type") == "checkout.session.completed":
        session_obj = event["data"]["object"] or {}
        metadata = session_obj.get("metadata") or {}

        upload_id = metadata.get("upload_id")
        token_code = metadata.get("token_used")
        amount_total = session_obj.get("amount_total", 0)
        customer_email = session_obj.get("customer_email") or "noemail@mailsized.com"

        if not upload_id:
            # If upload_id missing, ignore to prevent Stripe retries
            print("⚠️ Webhook ignored — missing upload_id in metadata.")
            return {"status": "ignored"}

        db = SessionLocal()
        try:
            job = repo.get_job_by_upload_id(db, upload_id)

            # ✅ Create fallback job if not found
            if not job:
                print(f"⚠️ No job found for {upload_id}, creating fallback.")
                job = repo.create_job(
                    db=db,
                    upload_id=upload_id,
                    filename="unknown",
                    email=customer_email,
                    provider="gmail",
                    size_bytes=0,
                    duration_sec=0.0,
                    price_cents=int(amount_total or 0),
                    priority=False,
                    transcript=False,
                    progress=0.0,
                    input_path=f"{upload_id}/unknown",
                )

            # ✅ Update payment info and mark queued
            job.price_cents = int(amount_total or job.price_cents)
            job.status = "queued"
            db.commit()

            # ✅ Enqueue for worker
            try:
                enqueue_job(
                    upload_id=job.upload_id,
                    filename=job.filename,
                    duration=job.duration_sec,
                    size=job.size_bytes,
                    provider=job.provider,
                    email=job.email,
                    priority=job.priority,
                )
                print(f"🟢 Enqueued job to Redis: {job.upload_id}")
            except Exception as e:
                print(f"🔴 Failed to enqueue job {job.upload_id}: {e}")

            # ✅ Consume promo token if one was used
            if token_code:
                try:
                    repo.use_token(db, token_code)
                    db.commit()
                    print(f"🎟️ Consumed token: {token_code}")
                except Exception as e:
                    print(f"⚠️ Failed to consume token {token_code}: {e}")

        finally:
            db.close()

    # Always return 200 to prevent Stripe retries
    return {"status": "ok"}
