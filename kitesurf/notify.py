"""Notification channels for wind alerts -- ntfy push and/or email.

Both are optional and independent: set NTFY_TOPIC for a push, or the
SMTP_* + NOTIFICATION_* vars for email, or both. Neither is required.
"""

import os
import smtplib
from email.mime.text import MIMEText

import httpx

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFICATION_FROM = os.environ.get("NOTIFICATION_FROM")
NOTIFICATION_TO = os.environ.get("NOTIFICATION_TO")


def _format_alert_line(alert: dict) -> str:
    return (
        f"{alert['spot_name']}: {alert['peak_score']:.0f} -- "
        f"{alert['start'].strftime('%a %d %b %H:%M')}-{alert['end'].strftime('%H:%M')} · "
        f"{alert['wind_kn']:.0f} kn · {alert['hours']:.0f}u aaneengesloten"
    )


def send_ntfy(alert: dict) -> None:
    if not NTFY_TOPIC:
        return
    title = f"{alert['spot_name']}: GO ({alert['peak_score']:.0f})"
    body = _format_alert_line(alert).split(" -- ", 1)[1]
    resp = httpx.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        content=body.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "kite"},
        timeout=15,
    )
    resp.raise_for_status()


def email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and NOTIFICATION_FROM and NOTIFICATION_TO)


def send_email_digest(alerts: list[dict]) -> None:
    """One email per run covering every new alert, rather than one per window."""
    if not alerts or not email_configured():
        return
    if len(alerts) == 1:
        subject = "Kitesurf alert: 1 nieuw GO-venster"
    else:
        subject = f"Kitesurf alert: {len(alerts)} nieuwe GO-vensters"
    body = "\n".join(_format_alert_line(a) for a in alerts)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = NOTIFICATION_FROM
    msg["To"] = NOTIFICATION_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(NOTIFICATION_FROM, [NOTIFICATION_TO], msg.as_string())
