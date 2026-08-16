import unittest

import pandas as pd

from kitesurf.tides import find_tide_events


def levels_df(heights, start="2026-08-16T00:00", freq="10min"):
    times = pd.date_range(start=start, periods=len(heights), freq=freq)
    return pd.DataFrame({"time": times, "height_cm": heights})


class TideEventTests(unittest.TestCase):
    def test_too_short_returns_nothing(self):
        self.assertEqual(find_tide_events(levels_df([10, 20])), [])

    def test_single_high_and_low(self):
        # ramps up to a peak, back down to a trough, back up
        heights = [0, 20, 40, 60, 40, 20, 0, -20, -40, -20, 0]
        events = find_tide_events(levels_df(heights))
        kinds = [e.kind for e in events]
        self.assertIn("high", kinds)
        self.assertIn("low", kinds)
        high = next(e for e in events if e.kind == "high")
        low = next(e for e in events if e.kind == "low")
        self.assertEqual(high.height_cm, 60)
        self.assertEqual(low.height_cm, -40)

    def test_flat_plateau_near_peak_does_not_duplicate(self):
        # two near-identical high points 10 minutes apart at the same peak
        heights = [0, 20, 40, 59, 60, 40, 20, 0]
        events = find_tide_events(levels_df(heights))
        highs = [e for e in events if e.kind == "high"]
        self.assertEqual(len(highs), 1)
        self.assertEqual(highs[0].height_cm, 60)

    def test_two_separate_highs_more_than_gap_apart_both_kept(self):
        # two clear peaks separated by more than MIN_EVENT_GAP (2h = 12 steps of 10min)
        heights = [0, 30, 0] + [0] * 20 + [0, 40, 0]
        events = find_tide_events(levels_df(heights))
        highs = [e for e in events if e.kind == "high"]
        self.assertEqual(len(highs), 2)

    def test_monotonic_series_has_no_events(self):
        heights = list(range(0, 100, 10))
        self.assertEqual(find_tide_events(levels_df(heights)), [])


if __name__ == "__main__":
    unittest.main()
