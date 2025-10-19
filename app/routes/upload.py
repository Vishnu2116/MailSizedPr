# app/routes/upload.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import uuid4

from app.utils.s3_utils import generate_presigned_upload_url
from app.db import SessionLocal
from app import repo

router = APIRouter()

MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2GB
FREE_TIER_BYTES = 50 * 1024 * 1024       # 50MB
MAX_DURATION_SEC = 20 * 60               # 20 minutes

class UploadRequest(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    duration_sec: float
    email: str


@router.post("/upload")
async def upload_file(req: UploadRequest):
    if req.size_bytes > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 2GB limit.")
    if req.duration_sec > MAX_DURATION_SEC:
        raise HTTPException(status_code=400, detail="Video exceeds 20 minutes.")
    if not req.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    upload_id = str(uuid4())
    presigned_url = generate_presigned_upload_url(upload_id, req.content_type)
    if not presigned_url:
        raise HTTPException(status_code=500, detail="Could not generate upload URL.")

    # 🆓 Assign tiers
    if req.size_bytes <= FREE_TIER_BYTES:
        # Free tier (<50 MB) → mark unpaid (-1)
        price_cents = -1
        tier_label = "free-tier"
    else:
        # Paid tier (>50 MB) → mark pending payment
        price_cents = 0
        tier_label = "paid-tier"

    db = SessionLocal()
    try:
        repo.create_job(
            db=db,
            upload_id=upload_id,
            filename=req.filename,
            email=req.email,
            provider="pending",
            size_bytes=req.size_bytes,
            duration_sec=req.duration_sec,
            price_cents=price_cents,
            priority=False,
            transcript=False,
            progress=0.0,
            input_path=f"{upload_id}/{req.filename}",
            token_used=None,
        )
    finally:
        db.close()

    return {
        "ok": True,
        "upload_id": upload_id,
        "presigned_url": presigned_url,
        "price_cents": price_cents,
        "tier": tier_label,
        "size_bytes": req.size_bytes,
        "duration_sec": req.duration_sec,
    }
