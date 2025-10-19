# app/utils/s3_utils.py
import boto3
import os
from uuid import uuid4
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
UPLOADS_BUCKET = os.getenv("UPLOADS_BUCKET")
UPLOAD_EXPIRY_SEC = 300  # 5 minutes
print("✅ DEBUG AWS_REGION:", AWS_REGION)
print("✅ DEBUG UPLOADS_BUCKET:", UPLOADS_BUCKET)


s3_client = boto3.client("s3", region_name=AWS_REGION)

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
            ExpiresIn=UPLOAD_EXPIRY_SEC
        )
        return url
    except Exception as e:
        print(f"⚠️ Error generating presigned URL: {e}")
        return None

def s3_upload_key(upload_id: str) -> str:
    return f"uploads/{upload_id}.mp4"
