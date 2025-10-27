# worker/worker.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import json
import re
import shutil
import time
import ssl
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
import boto3
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from app.utils.email_utils import send_output_email

# ─────────────── Load environment ───────────────
load_dotenv()

# ─────────────── Redis (TLS-aware connection) ───────────────
redis_url = urlparse(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
use_ssl = redis_url.scheme in ("rediss",)
print(f"🔗 Connecting to Redis at {redis_url.hostname}:{redis_url.port} (SSL={use_ssl})")

try:
    redis_client = redis.Redis(
        host=redis_url.hostname,
        port=redis_url.port or 6379,
        db=0,
        ssl=use_ssl,
        ssl_cert_reqs=ssl.CERT_NONE,  # Valkey uses managed certificates
        socket_connect_timeout=5,
        socket_timeout=10,
        retry_on_timeout=True,
    )
    redis_client.ping()
    print("✅ Redis connection successful!")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    redis_client = None

# ─────────────── AWS Clients ───────────────
s3 = boto3.client("s3")
UPLOAD_BUCKET = os.getenv("UPLOADS_BUCKET")
OUTPUT_BUCKET = os.getenv("OUTPUTS_BUCKET")

# ─────────────── PostgreSQL ───────────────
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_conn():
    """Always return a fresh DB connection (for long jobs)."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ─────────────── Folders ───────────────
WORK_DIR = Path("tmp")
WORK_DIR.mkdir(exist_ok=True)

# ─────────────── FFmpeg ───────────────
FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"
FFMPEG_LOCK = asyncio.Lock()


def _preexec_ulimits():
    """Restrict FFmpeg resource usage on worker."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (1800, 1800))
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_NOFILE, (512, 512))
    except Exception:
        pass


def percent_from_out_time_ms(line: str, duration: float) -> float:
    """Parse FFmpeg progress lines for % completion."""
    m = re.match(r"out_time_ms=(\d+)", line.strip())
    if m and duration > 0:
        ms = int(m.group(1))
        return min(99.0, (ms / 1_000_000.0) / duration * 100.0)
    return 0.0


def email_target_bitrates(duration_s: float, target_bytes: int, audio_kbps=96, overhead=0.92):
    """Compute target bitrate and resolution for email-friendly output."""
    if duration_s <= 0:
        duration_s = 1.0
    total_bits = target_bytes * 8 * overhead
    total_kbps = total_bits / duration_s / 1000.0
    v_kbps = max(120.0, total_kbps - audio_kbps)
    cap = 1280 if v_kbps >= 800 else 854
    return int(v_kbps), cap


def choose_target(provider: str, size_bytes: int) -> int:
    """Set target file size based on email provider limits."""
    cap_mb = {"gmail": 25, "outlook": 20, "other": 15}.get(provider, 15)
    return int((cap_mb - 1.5) * 1024 * 1024)


# ─────────────── Core Compression Logic ───────────────
async def compress_video(job: dict):
    upload_id = job["upload_id"]
    filename = job["filename"]
    duration = job["duration_sec"]
    size_bytes = job["size_bytes"]
    provider = job["provider"]
    priority = job.get("priority", False)

    # ✅ Fetch email from DB if missing
    email = job.get("email") or ""
    if not email:
        try:
            db_conn = get_db_conn()
            with db_conn.cursor() as cur:
                cur.execute("SELECT email FROM jobs WHERE upload_id=%s", (upload_id,))
                row = cur.fetchone()
                if row and row.get("email"):
                    email = row["email"]
                    print(f"📧 Retrieved email from DB: {email}")
            db_conn.close()
        except Exception as e:
            print(f"⚠️ Failed to fetch email from DB: {e}")

    if not email:
        email = "noemail@mailsized.com"

    print(f"🧾 Job data received: {job}")
    print(f"📧 Using email: {email}")

    target_bytes = choose_target(provider, size_bytes)
    v_kbps, cap = email_target_bitrates(duration, target_bytes)

    input_key = f"uploads/{upload_id}.mp4"
    output_key = f"outputs/{upload_id}_compressed.mp4"
    input_path = WORK_DIR / f"{upload_id}_input.mp4"
    output_path = WORK_DIR / f"{upload_id}_output.mp4"

    print(f"🎞️ Compressing {input_key} → {v_kbps} kbps, cap {cap}px")

    try:
        # ✅ Download input from S3
        s3.download_file(UPLOAD_BUCKET, input_key, str(input_path))

        vf = f"scale='min({cap},iw)':'-2'"
        audio_args = ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100"]

        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i", str(input_path),
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "main",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-threads", "1",
            "-x264-params", "ref=1:bframes=0:rc-lookahead=10",
            "-movflags", "+faststart",
            "-max_muxing_queue_size", "9999",
            *audio_args,
            "-b:v", f"{v_kbps}k",
            "-maxrate", f"{int(v_kbps * 1.5)}k",
            "-bufsize", f"{int(v_kbps * 2)}k",
            str(output_path),
        ]

        async with FFMPEG_LOCK:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                "-progress", "pipe:1",
                "-nostats",
                "-loglevel", "error",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=_preexec_ulimits,
            )
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                pct = percent_from_out_time_ms(line.decode(), duration)
                if pct:
                    print(f"Progress: {pct:.2f}%")

            await proc.wait()

        # ✅ Upload output to S3
        s3.upload_file(str(output_path), OUTPUT_BUCKET, output_key)

        # ✅ Generate 24-hour presigned URL
        expiry_seconds = 24 * 3600
        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": OUTPUT_BUCKET, "Key": output_key},
            ExpiresIn=expiry_seconds,
        )

        # ✅ Update DB
        try:
            db_conn = get_db_conn()
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status='done',
                        progress=100,
                        output_path=%s,
                        output_url=%s,
                        completed_at=NOW()
                    WHERE upload_id=%s
                    """,
                    (output_key, download_url, upload_id),
                )
                db_conn.commit()
            db_conn.close()
        except Exception as e:
            print(f"⚠️ Failed to update DB after compression: {e}")

        print(f"✅ Job {upload_id} completed and uploaded to {OUTPUT_BUCKET}")

        # ✅ Send completion email
        if email and "@" in email:
            try:
                send_output_email(email, download_url, filename)
            except Exception as e:
                print(f"❌ Email send failed: {e}")

    except Exception as e:
        print(f"❌ Compression failed: {e}")
        try:
            db_conn = get_db_conn()
            with db_conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET status='error', error=%s WHERE upload_id=%s",
                    (str(e), upload_id),
                )
                db_conn.commit()
            db_conn.close()
        except Exception as db_err:
            print(f"⚠️ Failed to record error in DB: {db_err}")

    finally:
        # ─────────────── Cleanup ───────────────
        try:
            if input_path.exists():
                input_path.unlink()
            if output_path.exists():
                output_path.unlink()
            now = time.time()
            for f in WORK_DIR.iterdir():
                try:
                    if f.is_file() and (now - f.stat().st_mtime > 900):
                        f.unlink()
                except Exception as inner_err:
                    print(f"⚠️ Skipping tmp cleanup for {f.name}: {inner_err}")
        except Exception as e:
            print(f"⚠️ Final cleanup failed: {e}")


# ─────────────── Worker Main Loop ───────────────
async def main():
    print("🚀 Worker started...")
    if not redis_client:
        print("❌ No Redis client available — exiting.")
        return

    while True:
        try:
            job_data = redis_client.blpop("mailsized_jobs", timeout=5)
            if job_data:
                _, payload = job_data
                job = json.loads(payload)
                await compress_video(job)
        except Exception as e:
            print(f"Worker loop error: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
