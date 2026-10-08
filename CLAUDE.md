# CLAUDE.md — rules for working on TSMIRP

TSMIRP (Tourist Safety Monitoring and Incident Response Platform) is a B.Tech final-year
prototype for Smart India Hackathon problem statement **SIH25002**. It is a
**decision-support platform, NOT a replacement for police or emergency services.**

## How we work
- Work in the numbered phases below, one phase at a time. After each phase: run the tests,
  summarise what exists and how to run it, then STOP and wait for "continue".
- When a .py or .js/.ts file is created or changed, show the COMPLETE file content, one file at
  a time, in creation order. No partial edits or "rest unchanged" placeholders.
- Explain each step briefly in plain language. The author is a beginner and must be able to
  explain every file in a viva.
- Never invent results. No accuracy numbers anywhere unless produced by a script that can be
  re-run. Where a target is unknown, write "to be determined experimentally".
- Commits are authored by the project owner only. Do NOT add Claude (or any AI) as author or
  co-author — no `Co-Authored-By` trailers, no "Generated with" footers.

## Hard scope rules
- Emergency dispatch, SMS and e-mail are SIMULATED (sandbox adapters that write to the database
  and log). Label this in the UI and README. Never contact real emergency services.
- Risk score is a relative decision-support estimate, never a "prediction that a crime will
  occur". UI wording must reflect that.
- Location is collected only after explicit, revocable consent. Authorities see a tourist's
  location only with consent or during an active SOS.
- Data is open or SYNTHETIC. Every synthetic dataset and every result on it must be labelled
  "synthetic". Do not claim real-world accuracy.
- Do not train on arrests or enforcement-derived labels (bias-feedback risk).
- Blockchain digital ID is out of scope. Use a time-bound signed QR credential (JWT) and a
  hash-chained audit log instead.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, PostgreSQL 16 + PostGIS
  (GeoAlchemy2), Redis (pub/sub), WebSockets
- ML/NLP: scikit-learn (logistic regression baseline, random forest primary; XGBoost only if it
  clearly beats RF), TF-IDF + logistic regression for text; translation behind an interface
- Frontend: React + TypeScript (Vite), Leaflet + OpenStreetMap tiles (PWA dropped to keep the
  scope small). Tourist app and authority dashboard
- Auth: JWT access + refresh tokens, Argon2id or bcrypt; roles: tourist, operator, supervisor,
  administrator
- Infra: Docker Compose (api, postgres/postgis, redis, web), pytest, ruff, pre-commit, GitHub
  Actions CI. Local development on Windows also works without Docker (see README).

## Repository layout
- `backend/` — `app/{api,core,models,schemas,services,ml}`, `alembic/`, `tests/`
- `frontend/` — `src/{tourist,dashboard,shared}`
- `ml/` — data generation, training, evaluation, `artefacts/`
- `docs/` — architecture, API, privacy notes

## Database (12 tables, PostGIS geometry in EPSG:4326, GiST indexes)
Users, TouristProfiles (location_consent, consent_time), EmergencyContacts, IncidentCategories,
Incidents (description, language, severity, status, is_sos, confidence), IncidentLocations
(Point, accuracy_m, recorded_at, expires_at), RiskZones (Polygon, base_level), RiskPredictions
(zone_id, time_bin, score, level, model_version), ResponseResources (type, Point, source,
availability_sim), ResponseAssignments, Notifications, AuditLogs.
Incident statuses: NEW, ACKNOWLEDGED, ASSIGNED, EN_ROUTE, RESOLVED, CLOSED.

## API
All endpoints require auth except register/login. Enforce object-level authorisation.
Rate-limit login, SOS, classify.
POST /auth/register, POST /auth/login, POST /tourist/location, GET /tourist/location/{id},
POST /incidents, GET /incidents, GET /incidents/{id}, POST /incidents/{id}/assign,
PATCH /incidents/{id}/status, POST /sos, GET /risk-zone?bbox=,
GET /nearby-resources?lat=&lon=&type=&k=, POST /risk/predict, POST /incident/classify,
POST /assistant/query, GET /analytics/summary, WS /ws/dashboard.

## Core logic
1. Geofencing server-side: ignore poor-accuracy fixes; ST_Contains/ST_DWithin vs RiskZones;
   dwell/debounce; alert only for High and Critical; log geofence events.
2. Risk levels from calibrated score in [0,1]: Low <0.25, Moderate <0.50, High <0.75,
   Critical >=0.75 (initial assumptions, configurable).
3. Classification: 9 categories (theft, harassment, medical emergency, accident, lost person,
   suspicious activity, natural disaster, fire, other) + confidence + suggested department.
   Low confidence => human review. SOS bypasses classification.
4. Severity rules LOW/MEDIUM/HIGH/CRITICAL (see project brief). Operators can override; log it.
5. Resource recommendation: PostGIS KNN (<->) on geography + capability + simulated
   availability; verify against brute-force Haversine in tests. Distances are straight-line.
6. SOS: cancel window -> location -> CRITICAL incident -> Redis -> dashboard WS -> sandbox
   notify contacts -> nearest resource -> operator assigns (simulated) -> status to tourist.
7. Multilingual: language detection; Hindi + romanised Hindi; translate-then-classify behind a
   Translator interface; measure romanised accuracy separately.
8. Assistant: curated knowledge base; never invent numbers; include 112 and 1363.
9. Hash-chained audit log for sensitive actions.

## Data and ML
- Seeded, documented synthetic generators for ONE demo area. OSM police/hospital import with
  ODbL attribution. Open-Meteo optional with fallbacks. Chicago crimes data only to test code.
- Risk model: grid cell x time bin, chronological split + blocked spatial CV, class weights,
  calibration, full metric set. Simplest model within one std of the best. Versioned artefacts;
  model_version stored in RiskPredictions. One-command reproducible training with fixed seeds.

## Phases (stop after each)
0. Repo scaffold, Docker Compose, CI, CLAUDE.md, health endpoint, DB + Alembic baseline.
1. Auth, roles, tourist profile, consent flags, RBAC tests, audit log.
2. Incident model + API + status lifecycle + dashboard WebSocket.
3. OSM resource import, nearest-resource ranking with Haversine cross-check tests.
4. Risk zones, geofence service, Leaflet map layers in both apps.
5. SOS flow with simulated dispatch and sandbox notifications.
6. Synthetic data; text classifier + severity rules; classification endpoint.
7. Risk model training, evaluation report, /risk/predict, level-based alerts.
8. Multilingual step and assistant.
9. Analytics, privacy controls, OWASP API Top 10 tests, final README (load test dropped to keep
   the scope small; stated in the README).
