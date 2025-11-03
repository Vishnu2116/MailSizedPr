# app/routes/download.py
from fastapi import APIRouter, HTTPException
from app.db import SessionLocal
from app import repo

router = APIRouter(prefix="/download", tags=["Download"])

@router.get("/{job_id}")
def get_download_url(job_id: str):
    """
    Returns the output_url for a completed job.
    Used by frontend script.js when polling or after SSE completion.
    """
    db = SessionLocal()
    try:
        job = repo.get_job_by_upload_id(db, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if not job.output_url:
            raise HTTPException(status_code=404, detail="Download not ready yet")

        return {"url": job.output_url}

    finally:
        db.close()
