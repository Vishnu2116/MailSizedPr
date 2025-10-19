# app/utils/email_utils.py
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_output_email(recipient: str, download_url: str, filename: str):
    """Send video download link via Mailgun (fallback to SMTP if Mailgun fails)."""
    app_name = "MailSized"

    subject = f"Your compressed video is ready 🎬"
    body = f"""
Hi there,

Your video "{filename}" has been successfully compressed and is ready for download.

👉 Download link (valid 24 hours):
{download_url}

Thanks for using {app_name}!
—
The {app_name} Team
"""

    # ─────────────── Mailgun Config ───────────────
    mailgun_key = os.getenv("MAILGUN_API_KEY")
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    sender = os.getenv("SENDER_EMAIL", "no-reply@mailsized.com")

    # ─────────────── SMTP Config ───────────────
    smtp_host = os.getenv("EMAIL_SMTP_HOST")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 587))
    smtp_user = os.getenv("EMAIL_USERNAME")
    smtp_pass = os.getenv("EMAIL_PASSWORD")

    # ─────────────── Try Mailgun first ───────────────
    if mailgun_key and mailgun_domain:
        try:
            resp = requests.post(
                f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
                auth=("api", mailgun_key),
                data={
                    "from": f"{app_name} <{sender}>",
                    "to": [recipient],
                    "subject": subject,
                    "text": body,
                },
                timeout=10,
            )
            resp.raise_for_status()
            print(f"✅ Email sent to {recipient} via Mailgun")
            return
        except Exception as e:
            print(f"❌ Mailgun email failed: {e}")

    # ─────────────── Fallback to SMTP ───────────────
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{app_name} <{sender}>"
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, [recipient], msg.as_string())

        print(f"✅ Email sent to {recipient} via SMTP ({smtp_host})")

    except Exception as e:
        print(f"❌ SMTP email failed: {e}")
