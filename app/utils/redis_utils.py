# app/utils/redis_utils.py
import os
import json
import redis
from urllib.parse import urlparse

# ───────────────────────────────────────────────
# Redis Connection (works for local & prod)
# ───────────────────────────────────────────────
redis_url = urlparse(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

redis_client = redis.Redis(
    host=redis_url.hostname,
    port=redis_url.port or 6379,
    db=0,
    decode_responses=True,
)

QUEUE_NAME = "mailsized_jobs"

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

    try:
        redis_client.rpush(QUEUE_NAME, json.dumps(job))
        print(f"📩 Queued job {upload_id} → Redis queue '{QUEUE_NAME}' (email={email})")
    except Exception as e:
        print(f"❌ Failed to enqueue job {upload_id}: {e}")
