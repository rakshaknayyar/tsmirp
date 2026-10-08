"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload   (from the backend folder)
"""

from fastapi import FastAPI

from app.api import admin, auth, health, tourist

app = FastAPI(
    title="TSMIRP API",
    version="0.1.0",
    description=(
        "Tourist Safety Monitoring and Incident Response Platform (SIH25002 prototype). "
        "Decision support only - not a replacement for police or emergency services. "
        "Dispatch, SMS and e-mail are SIMULATED."
    ),
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tourist.router)
app.include_router(admin.router)
