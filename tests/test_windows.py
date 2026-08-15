import unittest

import pandas as pd

from kitesurf.windows import compute_good_windows


def make_df(scores, start="2026-08-15T10:00", freq="1h"):
    times = pd.date_range(start=start, periods=len(scores), freq=freq)
    return pd.DataFrame(
        {
            "time": times,
            "score": scores,
            "wind_kn": [20] * len(scores),
            "gust_kn": [24] * len(scores),
            "dir_deg": [270] * len(scores),
        }
    )


class WindowTests(unittest.TestCase):
    def test_no_windows_below_threshold(self):
        df = make_df([80, 80, 80])
        windows = compute_good_windows(df, threshold=90, min_hours=3)
        self.assertTrue(windows.empty)

    def test_isolated_spike_does_not_qualify(self):
        df = make_df([10, 10, 95, 10, 10])
        windows = compute_good_windows(df, threshold=75, min_hours=3)
        self.assertTrue(windows.empty)

    def test_three_hour_run_qualifies(self):
        df = make_df([10, 80, 82, 81, 10])
        windows = compute_good_windows(df, threshold=75, min_hours=3)
        self.assertEqual(len(windows), 1)
        row = windows.iloc[0]
        self.assertEqual(row["hours"], 3)
        self.assertAlmostEqual(row["peak_score"], 82)

    def test_gap_in_timestamps_breaks_a_run(self):
        df = make_df([80, 80], start="2026-08-15T10:00")
        df2 = make_df([80], start="2026-08-15T14:00")  # 3h gap after the first two hours
        combined = pd.concat([df, df2], ignore_index=True)
        windows = compute_good_windows(combined, threshold=75, min_hours=3)
        self.assertTrue(windows.empty)

    def test_two_separate_runs_both_qualify(self):
        df = make_df([80, 80, 80, 10, 10, 90, 90, 90])
        windows = compute_good_windows(df, threshold=75, min_hours=3)
        self.assertEqual(len(windows), 2)


if __name__ == "__main__":
    unittest.main()
