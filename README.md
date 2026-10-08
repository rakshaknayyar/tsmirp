# TSMIRP — Tourist Safety Monitoring and Incident Response Platform

B.Tech final-year prototype for Smart India Hackathon problem statement **SIH25002**.

> **Decision support only.** TSMIRP is not a replacement for police or emergency services.
> In a real emergency, call **112**.

## Current status: Phase 5 (SOS, simulated dispatch, sandbox notifications)
- SOS button with a 5-second cancel window in the app; `POST /sos` creates a CRITICAL
  incident (`is_sos`, no category - SOS skips classification). An open SOS is returned
  instead of creating a duplicate. Rate-limited (3 per 10 min per account; the error says
  "call 112")
- Pressing SOS shares the location for that emergency even without general consent; it is
  deleted again when the SOS ends if consent is off
- **Sandbox only**: emergency contacts get a simulated SMS, the tourist a simulated e-mail
  (stored in `notifications`, logged with masked numbers, never sent anywhere)
- Dashboard: red active-SOS banner; acknowledge -> recommend -> assign (simulated dispatch)
- Every status change notifies the tourist in-app and live over `WS /ws/tourist`, which only
  ever carries events about the tourist's own incidents
- "I'm safe" (`POST /sos/{id}/cancel`) resolves the SOS, frees resources, tells contacts
  (sandbox SMS)

## Phase 4 (risk zones, geofencing, maps)
- Risk zones (PostGIS polygons, GiST index) with a RELATIVE level LOW / MODERATE / HIGH /
  CRITICAL. The Jaipur demo zones are **synthetic** (hand-made circles around public places,
  not crime data): `python -m app.cli seed-zones`
- `POST /tourist/location` (consent required): ignores fixes worse than 100 m accuracy, stores
  only the latest position, checks zones with `ST_Contains` (inside) and `ST_DWithin` (nearby)
- Geofence alerts only for HIGH / CRITICAL zones, after 60 s inside, at most once per entry
  with a 10-minute cooldown (all configurable assumptions); alerts go to the tourist (in-app),
  the audit log (no coordinates) and the live dashboard
- Staff can view a tourist's location only with consent or during an active SOS; every view
  is audited. Revoking consent deletes the stored location immediately
- Leaflet maps with OpenStreetMap tiles in both apps; the tourist app has a "demo position"
  option (simulated GPS at a Jaipur landmark) for testing from anywhere

## Phase 3 (response resources, nearest-resource ranking)
- Police stations, hospitals and fire stations for the demo area (Jaipur) imported from
  OpenStreetMap: `python -m app.cli import-osm --area jaipur`
- Nearest search with PostGIS KNN (`<->`) on geography; recommendations filtered by the
  category's department and ranked available -> matching capability -> nearer
- Tests cross-check PostGIS against a brute-force Haversine calculation
- `POST /incidents/{id}/assign` is a **simulated** dispatch: the decision is recorded, the
  resource is marked BUSY (simulated), nothing is sent anywhere
- All distances are **straight-line** approximations; real road distance is longer

### Known data limitations (observed in the Jaipur import, 2026-10-08)
- The import found 403 "hospitals", 22 police stations and 1 fire station. OpenStreetMap
  coverage is uneven: fire stations are clearly under-mapped.
- Some features tagged `amenity=hospital` are clinics or diagnostic centres, and some
  stations appear twice (e.g. a misspelt duplicate). The data is used as-is, not cleaned.

## Phase 2 (incidents, status lifecycle, live dashboard)
- Tourists report incidents (9 categories, each with a suggested department); a location can
  only be attached when location consent is on
- Status lifecycle NEW -> ACKNOWLEDGED -> ASSIGNED -> EN_ROUTE -> RESOLVED -> CLOSED, enforced
  by the API (invalid moves get 409); every change is audited
- Live authority dashboard over WebSocket (`/ws/dashboard`), via Redis pub/sub when Redis is
  running, otherwise in-process (fine for a single-machine demo)
- Severity is a provisional MEDIUM until the severity rules in Phase 6
- Web pages: `#/tourist` (log in or sign up, report, my incidents) and `#/dashboard`
  (staff log in, live incident list, status buttons)

### Earlier phases
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
| GET | /incident-categories | any logged-in user |
| POST | /incidents | tourist |
| GET | /incidents, /incidents/{id} | tourist (own only), staff (all) |
| PATCH | /incidents/{id}/status | operator, supervisor, administrator |
| WS | /ws/dashboard | operator, supervisor, administrator (token sent in first message) |
| WS | /ws/tourist | tourist (own incidents only; token sent in first message) |
| POST | /sos | tourist (rate-limited) |
| POST | /sos/{id}/cancel | tourist (own SOS only) |
| GET | /nearby-resources?lat=&lon=&type=&k= | any logged-in user |
| GET | /incidents/{id}/recommended-resources | operator, supervisor, administrator |
| POST | /incidents/{id}/assign | operator, supervisor, administrator (simulated dispatch) |
| POST | /tourist/location | tourist (consent required) |
| GET | /tourist/notifications | tourist (own only) |
| GET | /tourist/location/{user_id} | operator, supervisor, administrator (consent or active SOS; audited) |
| GET | /risk-zone?bbox=minLon,minLat,maxLon,maxLat | any logged-in user (GeoJSON) |

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
   python -m app.cli import-osm --area jaipur
   python -m app.cli seed-zones
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
  `app/services/notifier.py` contains no real SMS / e-mail provider on purpose.
- Response-unit availability (AVAILABLE / BUSY) is simulated; "assign" only records a decision.
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
