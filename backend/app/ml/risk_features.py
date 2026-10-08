"""Shared feature code for the risk model.

Used by BOTH the training script (ml/train_risk_model.py) and the API (app/services/risk.py),
so the model sees exactly the same features in training and in the app. This module does
not touch the database or the app settings, so the training script can import it alone.

Unit of prediction: one GRID CELL (about 1 km x 1 km) x one TIME BIN (6 hours, local time).
The model gives a score in [0, 1]: its calibrated estimate that at least one tourist incident
is reported in that cell during that bin. It is a RELATIVE decision-support estimate, not a
prediction that a crime will occur.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np

IST = timezone(timedelta(hours=5, minutes=30))  # India Standard Time (no daylight saving)
TIME_BINS = 4  # 00-06, 06-12, 12-18, 18-24 local time
BIN_HOURS = 24 // TIME_BINS
DEMO_BBOX = (26.80, 75.70, 27.00, 75.90)  # south, west, north, east (same as the OSM import)
CITY_CENTRE = (26.9124, 75.7873)
METRES_PER_DEGREE_LAT = 111_320

# Public landmarks the model knows about (used as features). The synthetic generator also
# has hotspots that are NOT in this list, so the model never sees the whole truth.
LANDMARKS = {
    "Hawa Mahal": (26.9239, 75.8267),
    "City Palace": (26.9258, 75.8237),
    "Jaipur Junction": (26.9196, 75.7878),
    "Amer Fort": (26.9855, 75.8513),
    "Jal Mahal": (26.9535, 75.8462),
    "Nahargarh Fort": (26.9373, 75.8155),
    "Albert Hall Museum": (26.9116, 75.8195),
    "Birla Mandir": (26.8921, 75.8155),
}

FEATURE_NAMES = [
    "dist_landmark_km",
    "landmarks_within_1km",
    "dist_centre_km",
    # The cell's share of 6-hour bins with an incident during the TRAINING period only.
    # Stored inside the model artefact, so training and the app use identical values.
    "cell_past_rate",
    "time_bin",
    "is_weekend",
    "month_sin",
    "month_cos",
    "tourist_season",
    "rain_mm",
    "temp_max_c",
]
TOURIST_SEASON_MONTHS = {10, 11, 12, 1, 2, 3}

# APPROXIMATE monthly climate of Jaipur, used ONLY when real weather is unavailable
# (Open-Meteo down, or in tests). Rough values for a fallback, not measured data.
FALLBACK_RAIN_MM = {
    1: 0.2, 2: 0.2, 3: 0.1, 4: 0.1, 5: 0.5, 6: 2.0,
    7: 7.0, 8: 6.0, 9: 3.0, 10: 0.5, 11: 0.1, 12: 0.1,
}  # fmt: skip
FALLBACK_TEMP_MAX_C = {
    1: 22, 2: 26, 3: 32, 4: 38, 5: 41, 6: 39,
    7: 34, 8: 32, 9: 33, 10: 33, 11: 29, 12: 24,
}  # fmt: skip


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    south: float
    west: float
    north: float
    east: float

    @property
    def centre(self) -> tuple[float, float]:
        return (self.south + self.north) / 2, (self.west + self.east) / 2

    def name(self, cell_size_m: int) -> str:
        return f"Grid cell r{self.row:02d} c{self.col:02d} ({cell_size_m} m)"


def grid_cells(cell_size_m: int) -> list[Cell]:
    """Square-ish cells of cell_size_m covering the demo area, row by row from the south."""
    south, west, north, east = DEMO_BBOX
    lat_step = cell_size_m / METRES_PER_DEGREE_LAT
    mean_lat = math.radians((south + north) / 2)
    lon_step = cell_size_m / (METRES_PER_DEGREE_LAT * math.cos(mean_lat))
    n_rows = math.ceil(round((north - south) / lat_step, 9))
    n_cols = math.ceil(round((east - west) / lon_step, 9))
    return [
        Cell(
            row=r,
            col=c,
            south=south + r * lat_step,
            west=west + c * lon_step,
            north=min(north, south + (r + 1) * lat_step),
            east=min(east, west + (c + 1) * lon_step),
        )
        for r in range(n_rows)
        for c in range(n_cols)
    ]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km; works on numbers or numpy arrays."""
    lat1, lon1, lat2, lon2 = (np.radians(v) for v in (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def static_features(lats: np.ndarray, lons: np.ndarray, past_rates: np.ndarray) -> np.ndarray:
    """Place features that do not change with time: shape (n_cells, 4)."""
    distances = np.stack(
        [haversine_km(lats, lons, lat, lon) for lat, lon in LANDMARKS.values()], axis=1
    )
    return np.column_stack(
        [
            distances.min(axis=1),
            (distances <= 1.0).sum(axis=1),
            haversine_km(lats, lons, *CITY_CENTRE),
            past_rates,
        ]
    )


def time_features(day: date, time_bin: int) -> list[float]:
    angle = 2 * math.pi * (day.month - 1) / 12
    return [
        float(time_bin),
        float(day.weekday() >= 5),
        math.sin(angle),
        math.cos(angle),
        float(day.month in TOURIST_SEASON_MONTHS),
    ]


def fallback_weather(day: date) -> tuple[float, float]:
    return FALLBACK_RAIN_MM[day.month], float(FALLBACK_TEMP_MAX_C[day.month])


def feature_matrix(
    static: np.ndarray, day: date, time_bin: int, rain_mm: float, temp_max_c: float
) -> np.ndarray:
    """All features for every cell for one (day, time bin): shape (n_cells, 11)."""
    n = static.shape[0]
    per_bin = np.array([*time_features(day, time_bin), rain_mm, temp_max_c])
    return np.column_stack([static, np.tile(per_bin, (n, 1))]).astype(np.float32)


def columns(names: list[str]) -> list[int]:
    """Positions of the named features (a model may use only some of them)."""
    return [FEATURE_NAMES.index(name) for name in names]


def bin_of(moment: datetime) -> tuple[date, int]:
    """Which (local day, time bin) a moment falls into."""
    local = moment.astimezone(IST)
    return local.date(), local.hour // BIN_HOURS


def bin_start(day: date, time_bin: int) -> datetime:
    return datetime(day.year, day.month, day.day, time_bin * BIN_HOURS, tzinfo=IST)


def level_name(score: float, thresholds: tuple[float, float, float]) -> str:
    """LOW < t1 <= MODERATE < t2 <= HIGH < t3 <= CRITICAL (initial thresholds 0.25/0.5/0.75)."""
    low, moderate, high = thresholds
    if score < low:
        return "LOW"
    if score < moderate:
        return "MODERATE"
    if score < high:
        return "HIGH"
    return "CRITICAL"
