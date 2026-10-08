# TSMIRP — Tourist Safety Monitoring and Incident Response Platform

B.Tech final-year prototype for Smart India Hackathon problem statement **SIH25002**.

> **Decision support only.** TSMIRP is not a replacement for police or emergency services.
> In a real emergency, call **112**.

## Current status: Phase 1 (auth, roles, consent, audit log)
- FastAPI backend with `GET /health` (checks API, PostgreSQL + PostGIS, Redis)
- Accounts with Argon2id password hashing and JWT access (15 min) + refresh (7 days) tokens
- Roles: tourist, operator, supervisor, administrator. Public sign-up creates tourists only;
  staff are created by an administrator
- Tourist profile with revocable location consent (off by default) and emergency contacts
- Hash-chained audit log of sensitive actions, with a verification endpoint
- Login rate limit (5 attempts per minute per IP + e-mail, in-memory)
- React + TypeScript frontend placeholder showing system health
- Docker Compose, GitHub Actions CI, ruff + pre-commit

### Endpoints so far
| Method | Path | Who |
|---|---|---|
| GET | /health | anyone |
| POST | /auth/register, /auth/login, /auth/refresh | anyone |
| GET | /auth/me | any logged-in user |
| GET, PUT | /tourist/profile | tourist (own profile only) |
| PUT | /tourist/consent | tourist |
| GET, POST | /tourist/emergency-contacts | tourist (own contacts only) |
| DELETE | /tourist/emergency-contacts/{id} | tourist (own contacts only) |
| POST | /admin/users | administrator |
| GET | /audit-logs, /audit-logs/verify | supervisor, administrator |

## Run locally on Windows (no Docker)

Requirements: PostgreSQL 16 with PostGIS, Python 3.11+, Node 22. Redis is optional until Phase 2.

1. Create a database named `tsmirp` (for example in pgAdmin).
2. Copy `.env.example` to `.env`, put your PostgreSQL password in it, and set `JWT_SECRET`
   to a long random value (the command to generate one is in the file).
3. Backend (from the `backend` folder):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   alembic upgrade head
   python -m app.cli create-admin --email you@example.org --name "Your Name"
   uvicorn app.main:app --reload
   ```
   `create-admin` asks for the password without showing it. Run it once.
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
