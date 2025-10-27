# app/routes/pay.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import SessionLocal
from app import repo
from app.utils.stripe_utils import create_checkout_session
from app.utils.redis_utils import enqueue_job  # for 100% free-token path

router = APIRouter()


class PayRequest(BaseModel):
    file_key: str
    email: str
    provider: str
    priority: bool = False
    transcript: bool = False
    promo_code: str | None = None
    size_bytes: int
    duration_sec: float
    price_cents: int
    filename: str


@router.post("/api/pay")
async def handle_payment(req: PayRequest):
    """
    Initializes payment flow:
      - Ensures a pending job exists BEFORE redirecting to Stripe (so webhook can find & enqueue it).
      - Validates promo tokens.
      - If token is 100% off → bypass Stripe, mark token used, enqueue immediately, return ok.
      - Otherwise → create Stripe Checkout Session and return its URL.
    """
    db = SessionLocal()
    token = None

    try:
        # 1️⃣ Ensure email is stored against this upload
        try:
            repo.update_job_email(db, req.file_key, req.email)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update email: {e}")

        # 2️⃣ Ensure a pending job row exists or update it
        job = repo.get_job_by_upload_id(db, req.file_key)
        if not job:
            job = repo.create_job(
                db=db,
                upload_id=req.file_key,
                filename=req.filename,
                email=req.email,
                provider=req.provider,
                size_bytes=req.size_bytes,
                duration_sec=req.duration_sec,
                price_cents=req.price_cents,  # provisional
                priority=req.priority,
                transcript=req.transcript,
                progress=0.0,
                input_path=f"{req.file_key}/{req.filename}",
            )
        else:
            # ✅ keep job info up to date
            job.filename = req.filename
            job.provider = req.provider
            job.size_bytes = req.size_bytes
            job.duration_sec = req.duration_sec
            job.price_cents = req.price_cents

        # 3️⃣ Token validation (only consume on 100% free)
        if req.promo_code:
            token = repo.get_token(db, req.promo_code.strip())
            if not token:
                raise HTTPException(status_code=400, detail="Invalid token.")
            if token.usage_count >= token.usage_limit:
                raise HTTPException(status_code=400, detail="Token already used.")

        db.commit()  # persist everything before Stripe call

        # 4️⃣ Handle 100% free token
        if token and int(getattr(token, "discount_percent", 0) or 0) == 100:
            try:
                repo.use_token(db, token.code)
                try:
                    job.status = "queued"
                except Exception:
                    pass
                db.commit()

                enqueue_job(
                    upload_id=job.upload_id,
                    filename=job.filename,
                    duration=job.duration_sec,
                    size=job.size_bytes,
                    provider=job.provider,
                    email=job.email,
                    priority=job.priority,
                )

                return {"ok": True, "job_id": job.id}
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Free token error: {e}")

        # 5️⃣ Normal paid flow → Stripe Checkout Session
        try:
            session = create_checkout_session(
                upload_id=req.file_key,
                email=req.email,
                amount_cents=req.price_cents,
                token_obj=token,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

        return {"checkout_url": session.url}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Payment init error: {e}")
    finally:
        db.close()
