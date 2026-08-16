"""The 6 kitesurf spots this app covers, all in Noord-Holland / Flevoland.

Wind-direction ranges are "onshore/cross-shore" windows for each spot's
water body orientation. They're rough approximations, not local knowledge --
verify against actual spot guides before relying on them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Spot:
    id: str
    name: str
    latitude: float
    longitude: float
    water_body: str
    is_coastal: bool  # True = North Sea (marine wave data available), False = inland lake
    # Wind FROM directions (degrees, 0-360) considered onshore/cross-shore and rideable.
    # A tuple (lo, hi) with lo > hi wraps through 360/0 (e.g. (300, 40)).
    good_wind_dir: tuple[float, float]


SPOTS: list[Spot] = [
    Spot(
        id="muiderberg",
        name="Muiderberg",
        latitude=52.3283,
        longitude=5.1225,
        water_body="IJmeer",
        is_coastal=False,
        good_wind_dir=(180, 300),  # S-SW-W-NW, blows onto the Muiderberg shore
    ),
    Spot(
        id="strand-horst",
        name="Strand Horst",
        latitude=52.3603,
        longitude=5.3966,
        water_body="Wolderwijd",
        is_coastal=False,
        good_wind_dir=(200, 320),  # SW-W-NW, onto the beach
    ),
    Spot(
        id="schellinkhout",
        name="Schellinkhout",
        latitude=52.6317,
        longitude=5.1203,
        water_body="Markermeer",
        is_coastal=False,
        good_wind_dir=(140, 260),  # S-SE-SW, blows across the Markermeer onto the north shore
    ),
    Spot(
        id="ijmuiden",
        name="IJmuiden",
        latitude=52.4581,
        longitude=4.5514,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(230, 350),  # SW-W-NW onshore
    ),
    Spot(
        id="wijk-aan-zee",
        name="Wijk aan Zee",
        latitude=52.4944,
        longitude=4.5981,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="zandvoort",
        name="Zandvoort",
        latitude=52.3730,
        longitude=4.5327,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
]

SPOTS_BY_ID: dict[str, Spot] = {s.id: s for s in SPOTS}
