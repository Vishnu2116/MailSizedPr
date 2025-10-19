# app/routes/events.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.db import SessionLocal
from app import repo
import asyncio
import json

router = APIRouter()

# ───────────── Event Stream (SSE) ─────────────
@router.get("/events/{job_id}")
async def stream_job_progress(request: Request, job_id: str):
    """Server-Sent Events to stream live job updates."""
    db = SessionLocal()

    async def event_generator():
        try:
            while True:
                # Break if client disconnects
                if await request.is_disconnected():
                    break

                job = repo.get_job_by_upload_id(db, job_id)
                if not job:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                    break

                payload = {
                    "status": job.status,
                    "progress": job.progress,
                    "message": "Processing…" if job.status == "queued" else job.status.capitalize(),
                }

                if job.output_url:
                    payload["download_url"] = job.output_url
                    payload["message"] = "Compression complete ✅"
                    yield f"data: {json.dumps(payload)}\n\n"
                    break

                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(2)
        finally:
            db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
