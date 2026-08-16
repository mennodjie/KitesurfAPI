import unittest

from kitesurf.kitesize import recommend_kite_size


class KiteSizeTests(unittest.TestCase):
    def test_lighter_wind_needs_bigger_kite(self):
        light = recommend_kite_size(75, 12)
        strong = recommend_kite_size(75, 30)
        self.assertGreater(light, strong)

    def test_heavier_rider_needs_bigger_kite_at_same_wind(self):
        light_rider = recommend_kite_size(60, 20)
        heavy_rider = recommend_kite_size(100, 20)
        self.assertGreaterEqual(heavy_rider, light_rider)

    def test_snaps_to_a_standard_size(self):
        from kitesurf.kitesize import STANDARD_SIZES

        self.assertIn(recommend_kite_size(73, 20), STANDARD_SIZES)

    def test_no_wind_returns_none(self):
        self.assertIsNone(recommend_kite_size(73, 0))
        self.assertIsNone(recommend_kite_size(73, None))

    def test_no_weight_returns_none(self):
        self.assertIsNone(recommend_kite_size(0, 20))
        self.assertIsNone(recommend_kite_size(None, 20))


if __name__ == "__main__":
    unittest.main()
