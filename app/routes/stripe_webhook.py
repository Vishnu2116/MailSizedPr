from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from app.db import SessionLocal
from app import repo

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, endpoint_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        upload_id = session["metadata"]["upload_id"]
        token_code = session["metadata"].get("token_used")

        db = SessionLocal()
        try:
            job = repo.get_job_by_upload_id(db, upload_id)
            if job:
                job.price_cents = session["amount_total"]
                job.status = "queued"
                db.commit()

            if token_code:
                repo.use_token(db, token_code)

        finally:
            db.close()

    return {"status": "ok"}
