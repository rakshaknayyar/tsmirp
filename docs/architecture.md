# Architecture (outline — expanded in Phase 9)

```
 Tourist app (PWA) ─┐                      ┌─ PostgreSQL 16 + PostGIS
                    ├─ HTTPS / WebSocket ─ FastAPI ─┤
 Authority dashboard┘                      └─ Redis (pub/sub, from Phase 2)
```

- **frontend/** — React + TypeScript (Vite). Tourist app and authority dashboard.
- **backend/** — FastAPI. `api/` = HTTP routes, `core/` = config + DB connection,
  `models/` = database tables, `schemas/` = request/response shapes, `services/` = business
  logic (geofencing, severity rules, simulated dispatch), `ml/` = loading trained models.
- **ml/** — scripts that generate SYNTHETIC data and train/evaluate models.
- **Database** — all geometry stored in EPSG:4326 (latitude/longitude) with GiST indexes.

## Status after Phase 0
Only `GET /health` exists. The baseline migration enables PostGIS; no tables yet.
