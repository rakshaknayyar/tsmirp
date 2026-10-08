"""SYNTHETIC spatio-temporal tourist incidents for the Jaipur demo area.

The generator is an inhomogeneous Poisson process. For every grid cell, day and 6-hour bin
the expected number of incidents is

    rate = (BACKGROUND_RATE + sum over hotspots of peak * exp(-d^2 / (2 * spread^2)))
           x TIME_OF_DAY[bin] x weekend factor x season factor x exp(-RAIN_EFFECT * rain_mm)
           x day noise (shared by the whole city, unknown to the model)

and the number of incidents is drawn from Poisson(rate). Each incident gets a random point
inside its cell, a random time inside its bin, and a category drawn from the mix of the
hotspots around it.

Documented assumptions (chosen by hand for a demo; NOT measured from real data):
- hotspot places, strengths and spreads below; three hotspots (Sindhi Camp, MI Road, World
  Trade Park) are NOT in the model's landmark features, so the model cannot see everything;
- more incidents in the evening, at weekends, in the tourist season (Oct-Mar), fewer in rain.
- These are tourist-REPORTED incidents. Nothing here is based on arrests or enforcement data.
All rows are labelled synthetic=True. Same seed and weather -> exactly the same incidents.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from app.ml.risk_features import BIN_HOURS, IST, TIME_BINS, Cell, haversine_km

CATEGORIES = [
    "theft",
    "harassment",
    "medical_emergency",
    "accident",
    "lost_person",
    "suspicious_activity",
    "natural_disaster",
    "fire",
    "other",
]


@dataclass(frozen=True)
class Hotspot:
    name: str
    lat: float
    lon: float
    peak: float  # expected incidents per 6-hour bin at the centre (before time effects)
    spread_km: float
    categories: dict[str, float]


HOTSPOTS = [
    Hotspot("Hawa Mahal / Johari Bazaar", 26.9225, 75.8255, 0.9, 0.6,
            {"theft": 0.45, "harassment": 0.25, "lost_person": 0.1, "other": 0.2}),
    Hotspot("Jaipur Junction station", 26.9196, 75.7878, 0.8, 0.5,
            {"theft": 0.5, "harassment": 0.2, "suspicious_activity": 0.15, "other": 0.15}),
    Hotspot("Amer Fort", 26.9855, 75.8513, 0.5, 0.6,
            {"accident": 0.3, "medical_emergency": 0.3, "lost_person": 0.25, "theft": 0.15}),
    Hotspot("City Palace", 26.9258, 75.8237, 0.35, 0.3,
            {"theft": 0.4, "lost_person": 0.3, "medical_emergency": 0.3}),
    Hotspot("Jal Mahal", 26.9535, 75.8462, 0.25, 0.4,
            {"theft": 0.3, "harassment": 0.3, "accident": 0.4}),
    Hotspot("Nahargarh road", 26.9373, 75.8155, 0.3, 0.5,
            {"harassment": 0.4, "accident": 0.4, "theft": 0.2}),
    # Hidden from the model (not in app.ml.risk_features.LANDMARKS):
    Hotspot("Sindhi Camp bus stand", 26.9230, 75.8000, 0.5, 0.4,
            {"theft": 0.5, "suspicious_activity": 0.3, "harassment": 0.2}),
    Hotspot("MI Road", 26.9150, 75.8070, 0.4, 0.5,
            {"theft": 0.4, "accident": 0.3, "other": 0.3}),
    Hotspot("World Trade Park", 26.8530, 75.8050, 0.3, 0.4,
            {"theft": 0.5, "lost_person": 0.3, "other": 0.2}),
]  # fmt: skip
BACKGROUND_RATE = 0.004
BACKGROUND_CATEGORIES = {
    "theft": 0.25, "accident": 0.2, "medical_emergency": 0.15, "harassment": 0.1,
    "suspicious_activity": 0.1, "fire": 0.05, "natural_disaster": 0.03, "lost_person": 0.05,
    "other": 0.07,
}  # fmt: skip
TIME_OF_DAY = np.array([0.3, 0.9, 1.0, 1.4])  # 00-06, 06-12, 12-18, 18-24
WEEKEND_FACTOR = 1.3
SEASON_FACTOR = {1: 1.4, 2: 1.4, 3: 1.4, 4: 0.8, 5: 0.8, 6: 0.8,
                 7: 0.9, 8: 0.9, 9: 0.9, 10: 1.4, 11: 1.4, 12: 1.4}  # fmt: skip
RAIN_EFFECT = 0.05  # each mm of rain lowers the rate by about 5 %
DAY_NOISE_SIGMA = 0.2
SEVERITY_DEFAULTS = {
    "theft": "MEDIUM", "harassment": "HIGH", "medical_emergency": "HIGH", "accident": "MEDIUM",
    "lost_person": "MEDIUM", "suspicious_activity": "LOW", "natural_disaster": "HIGH",
    "fire": "CRITICAL", "other": "LOW",
}  # fmt: skip
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class SyntheticIncident:
    occurred_at: datetime
    lat: float
    lon: float
    category: str
    severity: str
    synthetic: bool = True


def cell_rates_and_categories(cells: list[Cell]) -> tuple[np.ndarray, np.ndarray]:
    """Base rate per cell (n,) and category probabilities per cell (n, 9)."""
    lats = np.array([c.centre[0] for c in cells])
    lons = np.array([c.centre[1] for c in cells])
    base = np.full(len(cells), BACKGROUND_RATE)
    mix = np.outer(base, [BACKGROUND_CATEGORIES.get(c, 0.0) for c in CATEGORIES])
    for spot in HOTSPOTS:
        d = haversine_km(lats, lons, spot.lat, spot.lon)
        contribution = spot.peak * np.exp(-(d**2) / (2 * spot.spread_km**2))
        base += contribution
        mix += np.outer(contribution, [spot.categories.get(c, 0.0) for c in CATEGORIES])
    return base, mix / mix.sum(axis=1, keepdims=True)


def generate_incidents(
    cells: list[Cell], start: date, n_days: int, weather: dict[date, tuple[float, float]], seed: int
) -> list[SyntheticIncident]:
    rng = np.random.default_rng(seed)
    base, mix = cell_rates_and_categories(cells)
    days = [start + timedelta(days=i) for i in range(n_days)]
    day_factor = np.array(
        [
            (WEEKEND_FACTOR if d.weekday() >= 5 else 1.0)
            * SEASON_FACTOR[d.month]
            * np.exp(-RAIN_EFFECT * weather[d][0])
            for d in days
        ]
    ) * rng.lognormal(0.0, DAY_NOISE_SIGMA, size=n_days)
    rates = base[:, None, None] * day_factor[None, :, None] * TIME_OF_DAY[None, None, :]
    counts = rng.poisson(rates)  # shape (cells, days, bins)

    incidents = []
    for cell_i, day_i, bin_i in zip(*np.nonzero(counts), strict=True):
        cell, day = cells[cell_i], days[day_i]
        for _ in range(counts[cell_i, day_i, bin_i]):
            minute = int(rng.integers(0, BIN_HOURS * 60))
            category = CATEGORIES[rng.choice(len(CATEGORIES), p=mix[cell_i])]
            severity = SEVERITY_DEFAULTS[category]
            if rng.random() < 0.15 and severity != "CRITICAL":  # some reports are worse
                severity = LEVELS[LEVELS.index(severity) + 1]
            incidents.append(
                SyntheticIncident(
                    occurred_at=datetime(day.year, day.month, day.day, tzinfo=IST)
                    + timedelta(hours=int(bin_i) * BIN_HOURS, minutes=minute),
                    lat=float(rng.uniform(cell.south, cell.north)),
                    lon=float(rng.uniform(cell.west, cell.east)),
                    category=category,
                    severity=severity,
                )
            )
    incidents.sort(key=lambda i: i.occurred_at)
    return incidents


def label_matrix(
    incidents: list[SyntheticIncident], cells: list[Cell], start: date, n_days: int
) -> np.ndarray:
    """Turn incident POINTS back into labels, as a real pipeline would:
    labels[cell, day, bin] = 1 if at least one incident happened there."""
    labels = np.zeros((len(cells), n_days, TIME_BINS), dtype=np.int8)
    souths = np.array([c.south for c in cells])
    wests = np.array([c.west for c in cells])
    norths = np.array([c.north for c in cells])
    easts = np.array([c.east for c in cells])
    for incident in incidents:
        inside = np.nonzero(
            (souths <= incident.lat)
            & (incident.lat < norths)
            & (wests <= incident.lon)
            & (incident.lon < easts)
        )[0]
        local = incident.occurred_at.astimezone(IST)
        day_i = (local.date() - start).days
        if len(inside) and 0 <= day_i < n_days:
            labels[inside[0], day_i, local.hour // BIN_HOURS] = 1
    return labels


def write_csv(incidents: list[SyntheticIncident], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["occurred_at", "lat", "lon", "category", "severity", "synthetic"])
        for i in incidents:
            writer.writerow(
                [i.occurred_at.isoformat(), f"{i.lat:.6f}", f"{i.lon:.6f}", i.category,
                 i.severity, "true"]
            )  # fmt: skip
