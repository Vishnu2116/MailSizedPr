from fastapi import APIRouter
from pydantic import BaseModel
from app.db import SessionLocal
from app import repo

router = APIRouter()

class EmailUpdateRequest(BaseModel):
    upload_id: str
    email: str

@router.post("/update_email")
async def update_email(req: EmailUpdateRequest):
    db = SessionLocal()
    ok = repo.update_job_email(db, req.upload_id, req.email)
    db.close()
    return {"ok": ok}
