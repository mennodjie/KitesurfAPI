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


if __name__ == "__main__":
    unittest.main()
