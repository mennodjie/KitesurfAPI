import unittest

import pandas as pd

from kitesurf.alerts import find_new_alerts
from kitesurf.windows import WINDOW_COLUMNS

SPOT_NAMES = {"wijk-aan-zee": "Wijk aan Zee", "zandvoort": "Zandvoort"}


def make_window(start, hours=3, peak_score=90, wind_kn=20, dir_deg=270):
    start = pd.Timestamp(start)
    return {
        "start": start,
        "end": start + pd.Timedelta(hours=hours),
        "peak_score": peak_score,
        "avg_score": peak_score,
        "wind_kn": wind_kn,
        "gust_kn": wind_kn * 1.1,
        "dir_deg": dir_deg,
        "hours": hours,
    }


def windows_df(*rows):
    return pd.DataFrame(rows, columns=WINDOW_COLUMNS) if rows else pd.DataFrame(columns=WINDOW_COLUMNS)


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp("2026-08-15T09:00")

    def test_qualifying_window_within_range_alerts(self):
        windows_by_spot = {"wijk-aan-zee": windows_df(make_window("2026-08-16T12:00"))}
        alerts = find_new_alerts(windows_by_spot, SPOT_NAMES, threshold=75, within_days=3, already_notified=set(), now=self.now)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["spot_name"], "Wijk aan Zee")

    def test_below_threshold_does_not_alert(self):
        windows_by_spot = {"wijk-aan-zee": windows_df(make_window("2026-08-16T12:00", peak_score=60))}
        alerts = find_new_alerts(windows_by_spot, SPOT_NAMES, threshold=75, within_days=3, already_notified=set(), now=self.now)
        self.assertEqual(alerts, [])

    def test_beyond_within_days_does_not_alert(self):
        windows_by_spot = {"wijk-aan-zee": windows_df(make_window("2026-08-25T12:00"))}
        alerts = find_new_alerts(windows_by_spot, SPOT_NAMES, threshold=75, within_days=3, already_notified=set(), now=self.now)
        self.assertEqual(alerts, [])

    def test_already_notified_is_skipped(self):
        window = make_window("2026-08-16T12:00")
        windows_by_spot = {"wijk-aan-zee": windows_df(window)}
        key = f"wijk-aan-zee|{pd.Timestamp(window['start']).isoformat()}"
        alerts = find_new_alerts(windows_by_spot, SPOT_NAMES, threshold=75, within_days=3, already_notified={key}, now=self.now)
        self.assertEqual(alerts, [])

    def test_multiple_spots_both_alert(self):
        windows_by_spot = {
            "wijk-aan-zee": windows_df(make_window("2026-08-16T12:00")),
            "zandvoort": windows_df(make_window("2026-08-17T09:00")),
        }
        alerts = find_new_alerts(windows_by_spot, SPOT_NAMES, threshold=75, within_days=3, already_notified=set(), now=self.now)
        self.assertEqual(len(alerts), 2)


if __name__ == "__main__":
    unittest.main()
