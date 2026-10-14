"""Gmail SMTP email notifications for IoT equipment condition monitoring.

The MQTT subscriber calls the public send_* functions for condition/state
transitions only. Sending happens on a bounded background queue so network
SMTP delays do not block sensor callbacks. No credentials are printed.
"""

import logging
import os
import queue
import smtplib
import ssl
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").strip().lower() in ("1", "true", "yes")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()

logger = logging.getLogger(__name__)
_queue = queue.Queue(maxsize=100)
_lock = threading.Lock()
_started = False


def _send_email(subject, body):
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    # Never fall back to an unencrypted login.
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.send_message(msg)


def _worker():
    while True:
        subject, body = _queue.get()
        try:
            # Transient failures get at most three total attempts.
            for attempt in range(3):
                try:
                    _send_email(subject, body)
                    print(f"[EMAIL SENT] {subject}")
                    break
                except (smtplib.SMTPException, OSError) as exc:
                    logger.warning(
                        "[EMAIL ERROR] %s (attempt %d/3)",
                        type(exc).__name__, attempt + 1,
                    )
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        logger.error("[EMAIL] Notification discarded after 3 attempts")
        finally:
            _queue.task_done()


def start_email_worker():
    """Start one background worker; configuration errors disable email only."""
    global _started
    if not EMAIL_ENABLED:
        return
    if not (SMTP_HOST and SMTP_USER and SMTP_APP_PASSWORD and ALERT_EMAIL_TO):
        logger.error("[EMAIL] Missing configuration; notifications disabled")
        return
    with _lock:
        if _started:
            return
        thread = threading.Thread(target=_worker, name="iot-email", daemon=True)
        thread.start()
        _started = True
        print("[EMAIL] Background worker started")


def _enqueue(subject, body):
    if not EMAIL_ENABLED:
        return
    start_email_worker()
    if not _started:
        return
    try:
        _queue.put_nowait((subject, body))
        print(f"[EMAIL QUEUED] {subject}")
    except queue.Full:
        logger.error("[EMAIL] Queue full; notification dropped")


def send_equipment_alert(device_id, severity, previous_condition=None,
                         temperature=None, humidity=None, vibration=None,
                         timestamp=None):
    """Notify on equipment WARNING, CRITICAL, and RECOVERY transitions."""
    severity = str(severity).upper()
    subjects = {
        "WARNING": "WARNING - IoT Equipment Alert",
        "CRITICAL": "CRITICAL - IoT Equipment Alert",
        "RECOVERY": "RECOVERY - IoT Equipment Back to Normal",
    }
    if severity not in subjects:
        return
    at = timestamp or datetime.now(timezone.utc).isoformat()
    body = (
        "IoT EQUIPMENT CONDITION MONITORING SYSTEM\n"
        "-----------------------------------------\n"
        f"Alert: {severity}\n"
        f"Device: {device_id}\n"
        f"Previous Condition: {previous_condition or 'N/A'}\n"
        f"Temperature: {temperature if temperature is not None else 'N/A'} C\n"
        f"Humidity: {humidity if humidity is not None else 'N/A'} %\n"
        f"Vibration: {vibration if vibration is not None else 'N/A'}\n"
        f"Time: {at}\n"
    )
    _enqueue(subjects[severity], body)


def send_connectivity_alert(device_id, status, timestamp=None):
    """Notify on confirmed device OFFLINE and reconnection ONLINE transitions."""
    status = str(status).upper()
    if status not in ("OFFLINE", "ONLINE"):
        return
    subject = (
        "DEVICE OFFLINE - IoT Equipment Monitoring"
        if status == "OFFLINE"
        else "DEVICE ONLINE - IoT Equipment Monitoring"
    )
    at = timestamp or datetime.now(timezone.utc).isoformat()
    body = (
        "IoT EQUIPMENT CONNECTIVITY NOTIFICATION\n"
        "---------------------------------------\n"
        f"Device: {device_id}\n"
        f"Status: {status}\n"
        f"Time: {at}\n"
    )
    _enqueue(subject, body)
