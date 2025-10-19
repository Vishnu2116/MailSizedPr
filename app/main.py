# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from app.db import SessionLocal
from app import repo
import asyncio
import json
import os

# ────────────────────────────────
# Import Routers
# ────────────────────────────────
from app.routes import upload, pay, stripe_webhook, devtest, download, update_email

# ────────────────────────────────
# Initialize FastAPI
# ────────────────────────────────
app = FastAPI(title="MailSized API")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"])
)

# ────────────────────────────────
# Middleware
# ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["*"]
)

# ────────────────────────────────
# Mount Static Files
# ────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ────────────────────────────────
# Register Routers
# ────────────────────────────────
app.include_router(upload.router)
app.include_router(pay.router)
app.include_router(update_email.router)
app.include_router(stripe_webhook.router)
app.include_router(devtest.router)
app.include_router(download.router)

# ────────────────────────────────
# Template Renderer
# ────────────────────────────────
def render(template_name: str, request: Request, **context):
    template = env.get_template(template_name)
    return HTMLResponse(template.render(**context))

# ────────────────────────────────
# Basic Routes (HTML Pages)
# ────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/how-it-works", response_class=HTMLResponse)
def how_it_works(request: Request):
    return render("how-it-works.html", request)

@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return render("terms.html", request)

@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return render("privacy.html", request)

@app.get("/blogs", response_class=HTMLResponse)
def blogs(request: Request):
    return render("blogs.html", request)

@app.get("/blog/meet-mailsized", response_class=HTMLResponse)
def blog_meet_mailsized(request: Request):
    return render("blog-meet-mailsized.html", request)

@app.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    return render("contact.html", request)

# ────────────────────────────────
# SSE Route: /events/{job_id}
# ────────────────────────────────
@app.get("/events/{job_id}")
async def stream_job_progress(request: Request, job_id: str):
    """
    Server-Sent Events endpoint that streams live job progress to the frontend.
    Keeps a fresh DB session each tick to avoid stale cache.
    """
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            db = SessionLocal()
            try:
                job = repo.get_job_by_upload_id(db, job_id)
            finally:
                db.close()

            if not job:
                yield "data: " + json.dumps({"status": "error", "message": "Job not found"}) + "\n\n"
                break

            payload = {
                "status": job.status,
                "progress": job.progress,
                "message": "Processing…" if job.status == "queued" else job.status.capitalize(),
            }

            if job.output_url:
                payload["download_url"] = job.output_url
                payload["message"] = "Compression complete ✅"
                yield "data: " + json.dumps(payload) + "\n\n"
                break

            yield "data: " + json.dumps(payload) + "\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ────────────────────────────────
# Download Fallback: /download/{job_id}
# ────────────────────────────────
@app.get("/download/{job_id}")
def get_download_url(job_id: str):
    db = SessionLocal()
    try:
        job = repo.get_job_by_upload_id(db, job_id)
        if not job or not job.output_url:
            return JSONResponse({"error": "Download not ready"}, status_code=404)
        return {"url": job.output_url}
    finally:
        db.close()

# ────────────────────────────────
# Health Check Endpoint
# ────────────────────────────────
@app.get("/healthz")
def health_check():
    return {"status": "ok"}
