"""Request and response shapes for POST /risk/predict."""

import datetime as dt  # module import: a field called "date" would hide the type otherwise

from pydantic import BaseModel, ConfigDict, Field


class RiskPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None  # default: today (India time)
    # Optional weather for that day; missing values come from the approximate fallback table.
    rain_mm: float | None = Field(default=None, ge=0, le=500)
    temp_max_c: float | None = Field(default=None, ge=-10, le=55)


class RiskPredictResponse(BaseModel):
    model_version: str
    date: dt.date
    time_bins: list[dt.datetime]
    cells: int
    rows_written: int
    by_level: dict[str, int]
    weather_source: str
    note: str = (
        "Relative decision-support levels from a model trained on SYNTHETIC data; not a "
        "prediction that a crime will occur."
    )
