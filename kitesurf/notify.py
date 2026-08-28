"""Push notifications for wind alerts, via ntfy.sh."""

import os

import httpx

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


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
