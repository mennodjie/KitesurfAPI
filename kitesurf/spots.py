"""Kitesurf spots this app covers, across the Netherlands.

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
        latitude=52.5661,
        longitude=5.2814,
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
    Spot(
        id="scheveningen",
        name="Scheveningen",
        latitude=52.1042,
        longitude=4.2755,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="kijkduin",
        name="Kijkduin",
        latitude=52.0836,
        longitude=4.2144,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="hoek-van-holland",
        name="Hoek van Holland",
        latitude=51.9800,
        longitude=4.1150,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="ouddorp",
        name="Ouddorp (Kabbelaarsbank)",
        latitude=51.8270,
        longitude=3.9040,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="renesse",
        name="Renesse",
        latitude=51.7378,
        longitude=3.7936,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="brouwersdam",
        name="Brouwersdam",
        latitude=51.7500,
        longitude=3.8500,
        water_body="Grevelingenmeer",
        is_coastal=False,  # saltwater lagoon, not open North Sea -- no meaningful swell
        good_wind_dir=(200, 320),  # SW-W-NW onshore
    ),
    Spot(
        id="colijnsplaat",
        name="Colijnsplaat",
        latitude=51.5975,
        longitude=3.8460,
        water_body="Oosterschelde",
        is_coastal=False,  # sheltered tidal estuary
        good_wind_dir=(180, 300),  # S-SW-W onshore
    ),
    Spot(
        id="camperduin",
        name="Camperduin",
        latitude=52.7328,
        longitude=4.6425,
        water_body="North Sea",
        is_coastal=True,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="workum",
        name="Workum",
        latitude=52.9825,
        longitude=5.4396,
        water_body="IJsselmeer",
        is_coastal=False,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="makkum",
        name="Makkum",
        latitude=53.0567,
        longitude=5.4103,
        water_body="IJsselmeer",
        is_coastal=False,
        good_wind_dir=(210, 330),  # SW-W-NW onshore
    ),
    Spot(
        id="lauwersmeer",
        name="Lauwersmeer",
        latitude=53.3667,
        longitude=6.2167,
        water_body="Lauwersmeer",
        is_coastal=False,
        good_wind_dir=(220, 340),  # SW-W-NW onshore
    ),
]

SPOTS_BY_ID: dict[str, Spot] = {s.id: s for s in SPOTS}
