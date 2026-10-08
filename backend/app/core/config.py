"""Application settings.

All configuration comes from environment variables (or the .env file in the repository
root), so no passwords or secrets are written in the code.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# backend/app/core/config.py -> parents[3] is the repository root, where .env lives.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "tsmirp"

    redis_url: str = "redis://localhost:6379/0"
    # Live dashboard events: "redis" = Redis pub/sub (required), "memory" = inside this API
    # process only, "auto" = Redis if it is reachable at startup, otherwise memory.
    event_backend: Literal["auto", "redis", "memory"] = "auto"

    # Stored locations expire after this many days (initial assumption, configurable).
    location_retention_days: int = 30

    # Resources further away than this are never recommended (straight-line metres;
    # initial assumption, configurable). Without it, an AVAILABLE unit hundreds of km away
    # would outrank a BUSY one next door.
    recommend_max_distance_m: float = 25_000

    # Geofencing (initial assumptions, configurable; see app/services/geofence.py).
    geofence_max_accuracy_m: float = 100  # fixes less accurate than this are ignored
    geofence_dwell_seconds: int = 60  # must stay inside this long before an alert
    geofence_cooldown_seconds: int = 600  # no repeat alert for the same zone within this
    geofence_near_m: float = 200  # zones this close are reported as "nearby" (no alert)
    geofence_stale_seconds: int = 600  # a gap longer than this between fixes restarts dwell

    # SOS (initial assumptions, configurable; see app/services/sos.py).
    sos_rate_limit: int = 3  # SOS requests per user per window (the UI then says: call 112)
    sos_rate_window_seconds: int = 600
    sos_last_location_max_age_seconds: int = 600  # reuse a shared location this recent

    # Text classifier (trained by `python -m ml.train_text_classifier`).
    text_model_dir: Path = REPO_ROOT / "ml" / "artefacts" / "text_classifier"
    # Suggestions below this (calibrated) confidence are flagged for human review.
    # Initial assumption; to be determined experimentally on real, labelled reports.
    classify_review_threshold: float = 0.5
    classify_rate_limit: int = 30  # classification requests per user per window
    classify_rate_window_seconds: int = 60

    # Risk model (trained by `python -m ml.train_risk_model`).
    risk_model_dir: Path = REPO_ROOT / "ml" / "artefacts" / "risk_model"
    # Score thresholds LOW < t1 <= MODERATE < t2 <= HIGH < t3 <= CRITICAL
    # (initial assumptions from the project brief; configurable).
    risk_level_thresholds: tuple[float, float, float] = (0.25, 0.50, 0.75)

    # No default on purpose: the API refuses to start without a real secret.
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Login rate limit: at most this many attempts per window, per IP address + e-mail.
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60

    @property
    def database_url(self) -> URL:
        # URL.create escapes special characters in the password for us.
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = Settings()
