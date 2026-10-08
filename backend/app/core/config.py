"""Application settings.

All configuration comes from environment variables (or the .env file in the repository
root), so no passwords are written in the code.
"""

from pathlib import Path

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
