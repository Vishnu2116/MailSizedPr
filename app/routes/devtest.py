# app/routes/devtest.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import SessionLocal
from app import repo
import redis
import json
import os
from urllib.parse import urlparse

router = APIRouter()

# ───────────── Redis Setup ─────────────
redis_url = urlparse(os.getenv("REDIS_URL"))
redis_client = redis.Redis(
    host=redis_url.hostname,
    port=redis_url.port,
    db=0,
    decode_responses=True
)

# ───────────── Request Model ─────────────
class DevTestRequest(BaseModel):
    upload_id: str
    provider: str
    priority: bool = False
    transcript: bool = False
    token: str = "DEVTEST"  # default

# ───────────── Route: /devtest ─────────────
@router.post("/devtest")
def apply_devtest(req: DevTestRequest):
    # Validate token
    if req.token.strip().upper() != "DEVTEST":
        raise HTTPException(status_code=400, detail="Invalid token")

    db = SessionLocal()
    try:
        # Fetch job from DB
        job = repo.get_job_by_upload_id(db, req.upload_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Always allow DEVTEST (even for free tier)
        print(f"⚙️ Forcing compression via DEVTEST (price_cents={job.price_cents})")

        # Update job fields directly using ORM model
        job.status = "queued"
        job.price_cents = 0
        job.provider = req.provider.lower()
        job.priority = req.priority
        job.transcript = req.transcript
        job.token_used = "DEVTEST"
        db.commit()

        # Push job details to Redis queue
        redis_payload = {
            "upload_id": job.upload_id,
            "filename": job.filename,
            "duration_sec": job.duration_sec,
            "size_bytes": job.size_bytes,
            "provider": req.provider,
            "email": job.email,
            "priority": req.priority,
        }
        redis_client.rpush("mailsized_jobs", json.dumps(redis_payload))

        return {
            "ok": True,
            "message": "Job queued with DEVTEST token",
            "job_id": job.id
        }

    except Exception as e:
        print("❌ DEVTEST error:", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    finally:
        db.close()
