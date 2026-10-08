"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload   (from the backend folder)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    admin,
    assistant,
    auth,
    classify,
    health,
    incidents,
    resources,
    risk,
    sos,
    tourist,
    ws,
)
from app.services.events import event_bus


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await event_bus.start()  # connect to Redis (or fall back to in-process events)
    yield
    await event_bus.stop()


app = FastAPI(
    title="TSMIRP API",
    version="0.1.0",
    description=(
        "Tourist Safety Monitoring and Incident Response Platform (SIH25002 prototype). "
        "Decision support only - not a replacement for police or emergency services. "
        "Dispatch, SMS and e-mail are SIMULATED."
    ),
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tourist.router)
app.include_router(incidents.router)
app.include_router(classify.router)
app.include_router(resources.router)
app.include_router(risk.router)
app.include_router(sos.router)
app.include_router(ws.router)
app.include_router(admin.router)
app.include_router(assistant.router)
