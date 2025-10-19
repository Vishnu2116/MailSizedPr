# app/routes/pay.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import SessionLocal
from app import repo
from app.utils.stripe_utils import create_checkout_session

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
    db = SessionLocal()

    # ✅ Immediately update email for this job before doing anything else
    try:
        repo.update_job_email(db, req.file_key, req.email)
        db.commit()
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"Failed to update email: {e}")

    # ─────────── Token Validation ───────────
    token = None
    if req.promo_code:
        token = repo.get_token(db, req.promo_code.strip())
        if not token:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid token.")
        if token.usage_count >= token.usage_limit:
            db.close()
            raise HTTPException(status_code=400, detail="Token already used.")

    # ─────────── 100% Free Token (Bypass Stripe) ───────────
    if token and token.discount_percent == 100:
        try:
            job = repo.create_job(
                db=db,
                upload_id=req.file_key,
                filename=req.filename,
                email=req.email,
                provider=req.provider,
                size_bytes=req.size_bytes,
                duration_sec=req.duration_sec,
                price_cents=0,
                priority=req.priority,
                transcript=req.transcript,
                progress=0.0,
                input_path=f"{req.file_key}/{req.filename}",
                token_used=token.code,
            )
            repo.use_token(db, token.code)
            db.commit()
            return {"ok": True, "job_id": job.id}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Free token error: {e}")
        finally:
            db.close()

    # ─────────── Regular Stripe Payment ───────────
    try:
        session = create_checkout_session(
            upload_id=req.file_key,
            email=req.email,
            amount_cents=req.price_cents,
            token_obj=token,  # pass full token object, not just code
        )

        db.close()
        return {"checkout_url": session.url}

    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")
