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

    # Check if token is provided and valid
    token = None
    if req.promo_code:
        token = repo.get_token(db, req.promo_code.strip())
        if not token:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid token.")
        if token.usage_count >= token.usage_limit:
            db.close()
            raise HTTPException(status_code=400, detail="Token already used.")

    # 100% free token (bypass Stripe)
    if token and token.discount_percent == 100:
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
        db.close()
        return {"ok": True, "job_id": job.id}

    # Proceed with Stripe payment
    try:
        session = create_checkout_session(
            upload_id=req.file_key,
            email=req.email,
            amount_cents=req.price_cents,
            token=token.code if token else None,
        )
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

    db.close()
    return {"checkout_url": session.url}
