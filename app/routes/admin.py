# app/routes/admin.py
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import repo
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ────────────────────────────────
# Render Dashboard (Session Protected)
# ────────────────────────────────
@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    """Render dashboard only if logged in as admin."""
    if not request.session.get("is_admin"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("adminDashboard.html", {"request": request})


# ────────────────────────────────
# Dashboard Summary
# ────────────────────────────────
@router.get("/admin/summary")
def get_summary(db: Session = Depends(get_db)):
    jobs = db.query(repo.Job).all()
    tokens = db.query(repo.Token).all()

    total_jobs = len(jobs)
    completed_jobs = sum(1 for j in jobs if j.status == "done")
    total_revenue = sum(j.price_cents for j in jobs if j.status == "done") / 100
    active_tokens = sum(1 for t in tokens if t.usage_count < t.usage_limit)

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "total_revenue": round(total_revenue, 2),
        "active_tokens": active_tokens,
    }


# ────────────────────────────────
# Jobs List
# ────────────────────────────────
@router.get("/admin/jobs")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(repo.Job).order_by(repo.Job.created_at.desc()).limit(100).all()
    return [
        {
            "id": j.id,
            "filename": j.filename,
            "email": j.email,
            "status": j.status,
            "provider": j.provider,
            "price": j.price_cents / 100,
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": j.completed_at.strftime("%Y-%m-%d %H:%M:%S") if j.completed_at else None,
            "token_used": j.token_used,
        }
        for j in jobs
    ]


# ────────────────────────────────
# Tokens List
# ────────────────────────────────
@router.get("/admin/tokens")
def get_tokens(db: Session = Depends(get_db)):
    tokens = db.query(repo.Token).order_by(repo.Token.created_at.desc()).all()
    return [
        {
            "code": t.code,
            "discount_percent": t.discount_percent,
            "usage_limit": t.usage_limit,
            "usage_count": t.usage_count,
            "status": "active" if t.usage_count < t.usage_limit else "expired",
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for t in tokens
    ]


# ────────────────────────────────
# Create Token
# ────────────────────────────────
@router.post("/admin/token/create")
def create_token(
    name: str = Form(...),
    usage_limit: int = Form(1),
    discount_percent: int = Form(100),
    db: Session = Depends(get_db),
):
    code = f"{name}-{os.urandom(3).hex().upper()}"
    token = repo.create_token(
        db, code=code, discount_percent=discount_percent, usage_limit=usage_limit
    )
    return {"ok": True, "code": token.code}
