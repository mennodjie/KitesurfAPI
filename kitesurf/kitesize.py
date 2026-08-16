"""Rough kite-size suggestion from rider weight and wind speed.

Kite lift doesn't scale linearly with wind speed (closer to speed-squared
in the underlying physics), but simple weight/wind formulas are what most
public kite-size calculators actually use in practice -- riders adjust
bar pressure/depower within a size, so a rough size band is more useful
than false precision. This is a starting point for gear choice, not a
substitute for your own judgement or a shop's fitting advice.
"""

# Calibrated against commonly published freeride/twin-tip size charts
# (~75kg rider: ~14m at 12kn, ~9m at 20kn, ~6-7m at 30kn).
SIZE_CONSTANT = 2.4

STANDARD_SIZES = [4, 5, 6, 7, 8, 9, 10, 12, 14, 17]


def recommend_kite_size(weight_kg: float, wind_kn: float | None) -> float | None:
    if not wind_kn or wind_kn <= 0 or not weight_kg or weight_kg <= 0:
        return None
    raw_size = SIZE_CONSTANT * weight_kg / wind_kn
    return min(STANDARD_SIZES, key=lambda size: abs(size - raw_size))
