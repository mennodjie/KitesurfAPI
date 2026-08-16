"""The 6 kitesurf spots this app covers, all in Noord-Holland / Flevoland.

Wind-direction ranges are cross-checked against real spot guides (NKV
spotkaart, kitesurfvereniging.nl, 35knots.com, driftbeachclub.nl, and
kitesurf-school write-ups for each named spot) rather than guessed from
shoreline orientation alone -- still verify locally before relying on them.
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
        # N/NW/NE (E marginal) work; south is offshore and gets too gusty -- the
        # opposite of due-south-favoring shoreline guesses. (hanglos.nl, 35knots.com)
        good_wind_dir=(300, 100),
    ),
    Spot(
        id="strand-horst",
        name="Strand Horst",
        latitude=52.3603,
        longitude=5.3966,
        water_body="Wolderwijd",
        is_coastal=False,
        # N/NW/W are best; most directions are rideable here except E/SE for
        # beginners. (driftbeachclub.nl, kitesurfvereniging.nl)
        good_wind_dir=(245, 15),
    ),
    Spot(
        id="schellinkhout",
        name="Schellinkhout",
        latitude=52.6317,
        longitude=5.1203,
        water_body="Markermeer",
        is_coastal=False,
        # W/SW/S/SE all work -- a broad, forgiving beginner spot. (kitegids.nl,
        # kitesurfvereniging.nl)
        good_wind_dir=(135, 270),
    ),
    Spot(
        id="ijmuiden",
        name="IJmuiden",
        latitude=52.4581,
        longitude=4.5514,
        water_body="North Sea",
        is_coastal=True,
        # SW-NW is best; uniquely for this stretch of coast, S also works here
        # because the bay shape keeps it from being straight offshore.
        # (kitesurfvereniging.nl, letskite.ch)
        good_wind_dir=(185, 330),
    ),
    Spot(
        id="wijk-aan-zee",
        name="Wijk aan Zee",
        latitude=52.4944,
        longitude=4.5981,
        water_body="North Sea",
        is_coastal=True,
        # SW is best (shelters behind the Noordpier), W still cross-shore; due
        # south is offshore and explicitly not advised. (kitesurfvereniging.nl,
        # northseakitesurfschool.nl)
        good_wind_dir=(200, 300),
    ),
    Spot(
        id="zandvoort",
        name="Zandvoort",
        latitude=52.3730,
        longitude=4.5327,
        water_body="North Sea",
        is_coastal=True,
        # A wide window: SW through W/NW/N and well into NE.
        # (kitegids.nl, northseakitesurfschool.nl)
        good_wind_dir=(210, 35),
    ),
]

SPOTS_BY_ID: dict[str, Spot] = {s.id: s for s in SPOTS}
