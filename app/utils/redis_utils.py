# app/utils/redis_utils.py
import os
import json
import redis
from urllib.parse import urlparse

# ─────────────── Redis connection ───────────────
redis_url = urlparse(os.getenv("REDIS_URL"))
redis_client = redis.Redis(
    host=redis_url.hostname,
    port=redis_url.port,
    db=0
)

def enqueue_job(upload_id, filename, duration, size, provider, email, priority=False):
    """
    Push a new job into the Redis queue for the worker.
    The worker will later fetch this and perform compression + email.
    """
    job = {
        "upload_id": upload_id,
        "filename": filename,
        "duration_sec": duration,
        "size_bytes": size,
        "provider": provider,
        "email": email,
        "priority": priority,
    }
    redis_client.rpush("mailsized_jobs", json.dumps(job))
    print(f"📩 Queued job {upload_id} → Redis (email={email})")
