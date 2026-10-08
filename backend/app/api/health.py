"""Health check endpoint: GET /health.

Reports whether the API is running and whether it can reach PostgreSQL (with PostGIS) and
Redis. Overall status is "ok" only when the database and PostGIS work. Redis is reported but
not required yet; it becomes required in Phase 2 (live dashboard updates).
Errors show only the error type, never connection details or passwords.
"""

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["health"])


def check_database(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return {"status": "unavailable", "error": type(exc).__name__}

    try:
        version = db.execute(text("SELECT PostGIS_Version()")).scalar_one()
    except Exception:
        db.rollback()
        return {
            "status": "ok",
            "postgis_version": None,
            "note": "PostGIS extension not enabled - run `alembic upgrade head`",
        }
    return {"status": "ok", "postgis_version": version}


def check_redis() -> dict:
    client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
        return {"status": "ok"}
    except redis.RedisError as exc:
        return {"status": "unavailable", "error": type(exc).__name__}
    finally:
        client.close()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    database = check_database(db)
    overall_ok = database["status"] == "ok" and database.get("postgis_version")
    return {
        "status": "ok" if overall_ok else "degraded",
        "api": "ok",
        "database": database,
        "redis": check_redis(),
    }
