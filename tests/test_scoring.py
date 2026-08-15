import unittest

from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS_BY_ID
from kitesurf.weather import HourPoint


def hour(**kwargs):
    defaults = dict(
        time="2026-08-15T12:00",
        wind_speed_kn=20,
        wind_gust_kn=23,
        wind_direction_deg=270,
        precipitation_mm=0,
        wave_height_m=None,
    )
    defaults.update(kwargs)
    return HourPoint(**defaults)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.wijk_aan_zee = SPOTS_BY_ID["wijk-aan-zee"]
        self.schellinkhout = SPOTS_BY_ID["schellinkhout"]

    def test_ideal_conditions_score_high(self):
        score = score_hour(self.wijk_aan_zee, hour())
        self.assertGreater(score, 90)

    def test_no_wind_scores_zero(self):
        score = score_hour(self.wijk_aan_zee, hour(wind_speed_kn=0))
        self.assertEqual(score, 0.0)

    def test_offshore_wind_penalised(self):
        onshore = score_hour(self.wijk_aan_zee, hour(wind_direction_deg=270))
        offshore = score_hour(self.wijk_aan_zee, hour(wind_direction_deg=90))
        self.assertGreater(onshore, offshore)

    def test_gusty_wind_penalised(self):
        smooth = score_hour(self.wijk_aan_zee, hour(wind_speed_kn=20, wind_gust_kn=22))
        gusty = score_hour(self.wijk_aan_zee, hour(wind_speed_kn=20, wind_gust_kn=35))
        self.assertGreater(smooth, gusty)

    def test_rain_penalised(self):
        dry = score_hour(self.wijk_aan_zee, hour(precipitation_mm=0))
        wet = score_hour(self.wijk_aan_zee, hour(precipitation_mm=3))
        self.assertGreater(dry, wet)

    def test_missing_data_does_not_crash(self):
        score = score_hour(
            self.wijk_aan_zee,
            hour(wind_speed_kn=None, wind_gust_kn=None, wind_direction_deg=None, precipitation_mm=None),
        )
        self.assertEqual(score, 0.0)

    def test_inland_spot_has_no_wave_component(self):
        score = score_hour(self.schellinkhout, hour(wind_direction_deg=200, wave_height_m=None))
        self.assertGreater(score, 0)

    def test_high_waves_penalised_for_coastal_spot(self):
        calm = score_hour(self.wijk_aan_zee, hour(wave_height_m=0.3))
        rough = score_hour(self.wijk_aan_zee, hour(wave_height_m=2.0))
        self.assertGreater(calm, rough)


if __name__ == "__main__":
    unittest.main()
