# TSMIRP — Tourist Safety Monitoring and Incident Response Platform

B.Tech final-year prototype for Smart India Hackathon problem statement **SIH25002**.

> **Decision support only.** TSMIRP is not a replacement for police or emergency services.
> In a real emergency, call **112**.

## Current status: Phase 0 (scaffold)
- FastAPI backend with `GET /health` (checks API, PostgreSQL + PostGIS, Redis)
- Alembic baseline migration (enables PostGIS)
- React + TypeScript frontend placeholder showing system health
- Docker Compose, GitHub Actions CI, ruff + pre-commit

## Run locally on Windows (no Docker)

Requirements: PostgreSQL 16 with PostGIS, Python 3.11+, Node 22. Redis is optional until Phase 2.

1. Create a database named `tsmirp` (for example in pgAdmin).
2. Copy `.env.example` to `.env` and put your PostgreSQL password in it.
3. Backend (from the `backend` folder):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   alembic upgrade head
   uvicorn app.main:app --reload
   ```
   Open http://localhost:8000/health and http://localhost:8000/docs
4. Tests (from `backend`, with the venv active): `pytest -v`
5. Frontend (from the `frontend` folder):
   ```
   npm install
   npm run dev
   ```
   Open http://localhost:5173

## Run with Docker (optional)
```
docker compose up --build
```
The containerised database is exposed on port 5433 so it does not clash with a local PostgreSQL.

## What is simulated
- Emergency dispatch, SMS and e-mail: **simulated** sandbox adapters (write to database and log only).
- Datasets: open or **synthetic**; results on synthetic data are labelled as such.
- Risk scores: relative decision-support estimates, not predictions that a crime will occur.

(Expanded in Phase 9.)

## Data attribution
Map data and imported police/hospital locations (from Phase 3): © OpenStreetMap contributors,
available under the Open Database License (ODbL). https://www.openstreetmap.org/copyright

## Repository layout
- `backend/` — FastAPI app, Alembic migrations, tests
- `frontend/` — React + TypeScript (tourist app and authority dashboard)
- `ml/` — synthetic data generation, training, evaluation
- `docs/` — architecture and privacy notes
