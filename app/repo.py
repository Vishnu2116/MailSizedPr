# app/repo.py
from sqlalchemy.orm import Session
from .models.models import Job, Token
from datetime import datetime


# ─────────── Jobs ───────────

def create_job(
    db: Session,
    upload_id: str,
    filename: str,
    email: str,
    provider: str,
    size_bytes: int,
    duration_sec: float,
    price_cents: int,
    priority: bool = False,
    transcript: bool = False,
    progress: float = 0.0,
    input_path: str = "",
    token_used: str | None = None,
) -> Job:
    job = Job(
        upload_id=upload_id,
        filename=filename,
        email=email,
        provider=provider,
        size_bytes=size_bytes,
        duration_sec=duration_sec,
        price_cents=price_cents,
        priority=priority,
        transcript=transcript,
        progress=progress,
        input_path=input_path,
        token_used=token_used,
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def update_job_status(db: Session, job_id: str, status: str, output_url: str = None):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None
    job.status = status
    if output_url:
        job.output_url = output_url
        job.completed_at = datetime.utcnow()
    db.commit()
    return job

def get_job_by_id(db: Session, job_id: str):
    return db.query(Job).filter(Job.id == job_id).first()

def get_job_by_upload_id(db: Session, upload_id: str):
    return db.query(Job).filter(Job.upload_id == upload_id).first()


# ─────────── Tokens ───────────

def get_token(db: Session, code: str):
    return db.query(Token).filter(Token.code == code).first()

def use_token(db: Session, code: str):
    token = db.query(Token).filter(Token.code == code).first()
    if not token:
        return None
    if token.usage_count >= token.usage_limit:
        return None
    token.usage_count += 1
    db.commit()
    return token

def create_token(db: Session, code: str, discount_percent: int = 100, usage_limit: int = 1):
    token = Token(code=code, discount_percent=discount_percent, usage_limit=usage_limit)
    db.add(token)
    db.commit()
    db.refresh(token)
    return token
