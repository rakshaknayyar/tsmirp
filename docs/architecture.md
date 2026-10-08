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

## Live dashboard events
Routes call `event_bus.publish(...)` after their database commit. With Redis running, the
event goes to the Redis channel `tsmirp:dashboard` and a background listener in each API
process forwards it to that process's connected dashboards. Without Redis (`EVENT_BACKEND=auto`
falls back), events are delivered inside the single API process.

## Design assumptions (to revisit with domain experts)
- Category -> suggested department lookup: theft, harassment, lost person, suspicious
  activity -> Police; medical emergency, accident -> Medical; fire -> Fire; natural disaster
  -> Disaster Management; other -> Tourist Helpdesk.
- Stored locations expire after 30 days (`LOCATION_RETENTION_DAYS`).
- Staff see an incident's location only while the reporter's consent is on, or for an SOS.
