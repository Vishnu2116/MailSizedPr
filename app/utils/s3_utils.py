# app/utils/s3_utils.py
import boto3
import os
import os.path
from uuid import uuid4
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
UPLOADS_BUCKET = os.getenv("UPLOADS_BUCKET")
OUTPUTS_BUCKET = os.getenv("OUTPUTS_BUCKET")
UPLOAD_EXPIRY_SEC = 300  # 5 minutes
DOWNLOAD_EXPIRY_SEC = 3600  # 1 hour

print("✅ DEBUG AWS_REGION:", AWS_REGION)
print("✅ DEBUG UPLOADS_BUCKET:", UPLOADS_BUCKET)
print("✅ DEBUG OUTPUTS_BUCKET:", OUTPUTS_BUCKET)

s3_client = boto3.client("s3", region_name=AWS_REGION)


# ───────────────────────────────
# Generate Presigned Upload URL
# ───────────────────────────────
def generate_presigned_upload_url(upload_id: str, content_type: str = "video/mp4") -> str:
    object_key = f"uploads/{upload_id}.mp4"
    try:
        url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": UPLOADS_BUCKET,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=UPLOAD_EXPIRY_SEC,
        )
        return url
    except Exception as e:
        print(f"⚠️ Error generating presigned upload URL: {e}")
        return None


def s3_upload_key(upload_id: str) -> str:
    return f"uploads/{upload_id}.mp4"


# ───────────────────────────────
# Generate Presigned Download URL
# ───────────────────────────────
def generate_presigned_download_url(output_key: str) -> str:
    """
    Generate a signed URL for downloading the output file,
    forcing the browser to download it (not stream it),
    and using the same filename as uploaded.
    """
    try:
        filename = os.path.basename(output_key)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": OUTPUTS_BUCKET,
                "Key": output_key,
                # Forces browser download with proper filename
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=DOWNLOAD_EXPIRY_SEC,
        )
        return url
    except Exception as e:
        print(f"⚠️ Error generating presigned download URL: {e}")
        return None
