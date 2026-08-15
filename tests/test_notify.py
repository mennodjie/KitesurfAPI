import email
import unittest
from unittest import mock

import pandas as pd

import kitesurf.notify as notify


def make_alert(spot_name="Wijk aan Zee", peak_score=90):
    start = pd.Timestamp("2026-08-16T12:00")
    return {
        "key": f"wijk-aan-zee|{start.isoformat()}",
        "spot_id": "wijk-aan-zee",
        "spot_name": spot_name,
        "start": start,
        "end": start + pd.Timedelta(hours=3),
        "peak_score": peak_score,
        "wind_kn": 20,
        "dir_deg": 270,
        "hours": 3,
    }


class NtfyTests(unittest.TestCase):
    @mock.patch.object(notify, "NTFY_TOPIC", None)
    @mock.patch("httpx.post")
    def test_no_topic_configured_skips_request(self, mock_post):
        notify.send_ntfy(make_alert())
        mock_post.assert_not_called()

    @mock.patch.object(notify, "NTFY_TOPIC", "my-topic")
    @mock.patch("httpx.post")
    def test_topic_configured_posts_to_ntfy(self, mock_post):
        mock_post.return_value.raise_for_status = mock.Mock()
        notify.send_ntfy(make_alert())
        mock_post.assert_called_once()
        self.assertIn("my-topic", mock_post.call_args[0][0])


class EmailTests(unittest.TestCase):
    def test_not_configured_by_default(self):
        self.assertFalse(notify.email_configured())

    @mock.patch.object(notify, "SMTP_HOST", "smtp.example.com")
    @mock.patch.object(notify, "SMTP_USERNAME", "user")
    @mock.patch.object(notify, "SMTP_PASSWORD", "pass")
    @mock.patch.object(notify, "NOTIFICATION_FROM", "bot@example.com")
    @mock.patch.object(notify, "NOTIFICATION_TO", "me@example.com")
    def test_configured_when_all_vars_set(self):
        self.assertTrue(notify.email_configured())

    @mock.patch("smtplib.SMTP")
    def test_no_alerts_does_not_send(self, mock_smtp):
        notify.send_email_digest([])
        mock_smtp.assert_not_called()

    @mock.patch.object(notify, "SMTP_HOST", "smtp.example.com")
    @mock.patch.object(notify, "SMTP_USERNAME", "user")
    @mock.patch.object(notify, "SMTP_PASSWORD", "pass")
    @mock.patch.object(notify, "NOTIFICATION_FROM", "bot@example.com")
    @mock.patch.object(notify, "NOTIFICATION_TO", "me@example.com")
    @mock.patch("smtplib.SMTP")
    def test_configured_with_alerts_sends_one_digest(self, mock_smtp):
        server = mock_smtp.return_value.__enter__.return_value
        notify.send_email_digest([make_alert(), make_alert(spot_name="Zandvoort")])
        server.login.assert_called_once_with("user", "pass")
        server.sendmail.assert_called_once()
        raw = server.sendmail.call_args[0][2]
        body = email.message_from_string(raw).get_payload(decode=True).decode("utf-8")
        self.assertIn("Wijk aan Zee", body)
        self.assertIn("Zandvoort", body)


if __name__ == "__main__":
    unittest.main()
