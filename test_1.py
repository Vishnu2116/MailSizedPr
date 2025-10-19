import redis, json
r = redis.Redis(host='localhost', port=6379, db=0)
r.rpush("mailsized_jobs", json.dumps({
    "upload_id": "1234-uuid",
    "filename": "video.mov",
    "duration_sec": 45.0,
    "size_bytes": 105_000_000,
    "provider": "gmail",
    "email": "test@example.com",
    "priority": False,
}))
