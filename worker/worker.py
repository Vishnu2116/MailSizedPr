# worker/worker.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import re
import shutil
import time
import ssl
import subprocess
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

# ─────────────── Redis ───────────────
redis_url = urlparse(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
use_ssl = redis_url.scheme in ("rediss",)
print(f"🔗 Connecting to Redis at {redis_url.hostname}:{redis_url.port} (SSL={use_ssl})")

try:
    redis_client = redis.Redis(
        host=redis_url.hostname,
        port=redis_url.port or 6379,
        db=0,
        ssl=use_ssl,
        ssl_cert_reqs=ssl.CERT_NONE,
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
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ─────────────── Folders ───────────────
WORK_DIR = Path("tmp")
WORK_DIR.mkdir(exist_ok=True)

FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"


# ─────────────── Progress Parser ───────────────
def percent_from_out_time_ms(line: str, duration: float) -> float:
    m = re.match(r"out_time_ms=(\d+)", line.strip())
    if not m or duration <= 0:
        return 0.0

    ms = int(m.group(1))
    pct = (ms / 1_000_000.0) / duration * 100.0
    return min(99.0, pct)


# ─────────────── Target Size (Option B Safe Limits) ───────────────
SAFE_CAPS_MB = {
    "gmail": 23.5,      # 25 MB minus safety
    "outlook": 18.5,    # 20 MB minus safety
    "other": 13.5       # 15 MB minus safety
}

def choose_target(provider: str) -> int:
    cap_mb = SAFE_CAPS_MB.get(provider, 13.5)
    return int(cap_mb * 1024 * 1024)


# ─────────────── Stable Bitrate Calc ───────────────
def safe_bitrate_calc(duration_s: float, target_bytes: int, audio_kbps=96):
    if duration_s < 5:
        duration_s = 5
    if duration_s > 7200:
        duration_s = 7200

    total_bits = target_bytes * 8 * 0.90
    total_kbps = total_bits / duration_s / 1000

    v_kbps = max(240.0, total_kbps - audio_kbps)

    cap = 1280 if v_kbps >= 800 else 854
    return int(v_kbps), cap


# ─────────────── Core Compression ───────────────
def compress_video(job):
    upload_id = job["upload_id"]
    filename = job["filename"]
    duration = job.get("duration_sec", 0)
    provider = job["provider"]

    # fetch email
    email = job.get("email", "")
    if not email:
        try:
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM jobs WHERE upload_id=%s", (upload_id,))
                row = cur.fetchone()
                if row:
                    email = row.get("email", "")
            conn.close()
        except:
            pass

    if not email:
        email = "noemail@mailsized.com"

    print(f"🧾 Job info: {job}")
    print(f"📧 Email: {email}")

    # Update DB: processing
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status='processing', progress=1 WHERE upload_id=%s",
                (upload_id,),
            )
            conn.commit()
        conn.close()
    except:
        pass

    # bitrate logic
    target_bytes = choose_target(provider)
    v_kbps, cap = safe_bitrate_calc(duration, target_bytes)

    input_key = f"uploads/{upload_id}.mp4"
    output_key = f"outputs/{upload_id}_compressed.mp4"

    input_path = WORK_DIR / f"{upload_id}_input.mp4"
    output_path = WORK_DIR / f"{upload_id}_output.mp4"

    print(f"🎞 Starting compression @ {v_kbps} kbps cap {cap}px (limit={target_bytes})")

    try:
        s3.download_file(UPLOAD_BUCKET, input_key, str(input_path))

        vf = f"scale='min({cap},iw)':'-2'"

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(input_path),
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-threads", "1",
            "-b:v", f"{v_kbps}k",
            "-maxrate", f"{int(v_kbps*1.5)}k",
            "-bufsize", f"{int(v_kbps*2)}k",
            "-c:a", "aac", "-b:a", "96k",
            "-fs", str(target_bytes),
            "-progress", "pipe:1",
            "-nostats",
            "-loglevel", "error",
            str(output_path),
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        last_update_time = time.time()
        last_pct = 1

        while True:
            line = proc.stdout.readline()
            if not line:
                break

            pct = percent_from_out_time_ms(line, duration)

            # Update if %
            if pct >= last_pct + 1 or (time.time() - last_update_time) >= 2:
                last_pct = pct
                last_update_time = time.time()

                print(f"Progress: {pct:.2f}%")

                try:
                    conn = get_db_conn()
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE jobs SET progress=%s WHERE upload_id=%s",
                            (pct, upload_id),
                        )
                        conn.commit()
                    conn.close()
                except:
                    pass

        proc.wait()

        # upload final file
        s3.upload_file(str(output_path), OUTPUT_BUCKET, output_key)

        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": OUTPUT_BUCKET, "Key": output_key},
            ExpiresIn=86400,
        )

        # final update
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs SET status='done', progress=100,
                output_path=%s, output_url=%s, completed_at=NOW()
                WHERE upload_id=%s
                """,
                (output_key, download_url, upload_id),
            )
            conn.commit()
        conn.close()

        print("✅ Finished job")

        if "@" in email:
            try:
                send_output_email(email, download_url, filename)
            except:
                pass

    except Exception as e:
        print(f"❌ Compression Failed: {e}")

        try:
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET status='error', error=%s WHERE upload_id=%s",
                    (str(e), upload_id),
                )
                conn.commit()
            conn.close()
        except:
            pass

    finally:
        try:
            if input_path.exists(): input_path.unlink()
            if output_path.exists(): output_path.unlink()
        except:
            pass


# ─────────────── SINGLE JOB WORKER ───────────────

def run_worker():
    print("🚀 Worker started (SINGLE-JOB MODE)")

    while True:
        try:
            job_data = redis_client.blpop("mailsized_jobs", timeout=3)
            if not job_data:
                time.sleep(1)
                continue

            _, payload = job_data
            job = json.loads(payload)

            print(f"📥 Picked job {job['upload_id']}")
            compress_video(job)

        except Exception as e:
            print(f"⚠ Worker loop error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        print("🛑 Stopped by user")
