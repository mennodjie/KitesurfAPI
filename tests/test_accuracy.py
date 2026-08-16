import unittest

from kitesurf.accuracy import MIN_SAMPLES_FOR_SUMMARY, circular_diff, summarize


def row(spot_id="zandvoort", forecast_wind=20, observed_wind=22, forecast_dir=270, observed_dir=280):
    return {
        "timestamp": "2026-08-16T12:00:00",
        "spot_id": spot_id,
        "forecast_wind_kn": forecast_wind,
        "observed_wind_kn": observed_wind,
        "forecast_dir_deg": forecast_dir,
        "observed_dir_deg": observed_dir,
    }


class CircularDiffTests(unittest.TestCase):
    def test_simple_case(self):
        self.assertEqual(circular_diff(10, 30), 20)

    def test_wraps_through_zero(self):
        self.assertEqual(circular_diff(350, 10), 20)

    def test_none_is_none(self):
        self.assertIsNone(circular_diff(None, 30))
        self.assertIsNone(circular_diff(30, None))

    def test_opposite_directions(self):
        self.assertEqual(circular_diff(0, 180), 180)


class SummarizeTests(unittest.TestCase):
    def test_empty_log(self):
        result = summarize([])
        self.assertTrue(result.empty)

    def test_below_min_samples_excluded(self):
        rows = [row() for _ in range(MIN_SAMPLES_FOR_SUMMARY - 1)]
        result = summarize(rows)
        self.assertTrue(result.empty)

    def test_at_min_samples_included_with_correct_stats(self):
        rows = [row(forecast_wind=20, observed_wind=22, forecast_dir=270, observed_dir=280) for _ in range(MIN_SAMPLES_FOR_SUMMARY)]
        result = summarize(rows)
        self.assertEqual(len(result), 1)
        r = result.iloc[0]
        self.assertEqual(r["samples"], MIN_SAMPLES_FOR_SUMMARY)
        self.assertEqual(r["mean_wind_error_kn"], 2.0)
        self.assertEqual(r["mean_dir_error_deg"], 10.0)

    def test_separates_by_spot(self):
        rows = [row(spot_id="zandvoort") for _ in range(MIN_SAMPLES_FOR_SUMMARY)] + [
            row(spot_id="ijmuiden") for _ in range(MIN_SAMPLES_FOR_SUMMARY)
        ]
        result = summarize(rows)
        self.assertEqual(set(result["spot_id"]), {"zandvoort", "ijmuiden"})


if __name__ == "__main__":
    unittest.main()
