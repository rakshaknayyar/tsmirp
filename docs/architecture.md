# Architecture

The diagram with all parts is in the README. Overview:

```
 Tourist app ───────┐                      ┌─ PostgreSQL 16 + PostGIS
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
- Department -> resource types: Police -> police station; Medical -> hospital; Fire -> fire
  station; Disaster Management -> fire station or police station; Tourist Helpdesk -> police
  station.
- Recommendation ranking: only resources within 25 km straight-line
  (`RECOMMEND_MAX_DISTANCE_M`); OFFLINE excluded; AVAILABLE before BUSY; matching capability first
  (medical emergency / accident prefer hospitals tagged `emergency=yes`); then nearer.
  The nearest 20 suitable resources (PostGIS KNN) are re-ranked.
- Resource availability is simulated: assigning marks a resource BUSY, resolving or closing
  the incident marks it AVAILABLE again.
- Demo area bounding box (Jaipur): south 26.80, west 75.70, north 27.00, east 75.90.
- Stored locations expire after 30 days (`LOCATION_RETENTION_DAYS`).
- Tourist location storage: the brief's 12 tables have no tourist-location table, so only the
  LATEST fix is kept as columns on `tourist_profiles` (no movement history). Geofence dwell
  state is a small JSON column there too.
- Geofence parameters: ignore fixes worse than 100 m; alert after 60 s dwell; 10 min cooldown
  per zone; "nearby" = within 200 m (`GEOFENCE_*` settings).
- Geofence dwell restarts if the previous fix is older than 10 minutes
  (`GEOFENCE_STALE_SECONDS`), so an old "inside since" time cannot trigger an instant alert.
- SOS: 5 s cancel window (in the app); 3 SOS per 10 min per account; a shared location up to
  10 min old is reused when the SOS itself has none; an open SOS is returned instead of a
  duplicate; "I'm safe" may resolve the SOS from any open status (special path outside the
  operator lifecycle).
- Text classification: TF-IDF + logistic regression, sigmoid-calibrated, trained on synthetic
  English text only. Review threshold 0.5 (initial assumption).
  If no model is trained, new reports stay uncategorised and are flagged for review.
- Languages: detected by rules (Devanagari letters -> "hi"; 2+ typical romanised Hindi words
  making up a quarter of the words -> "hi-Latn"; else "en") unless the client gives one.
  Hindi is translated word by word with a hand-written list (app/ml/hindi_glossary.py) behind
  the Translator interface, then classified; severity rules read the original + the English.
  If the translation contains no English words, confidence is set to 0 (always reviewed).
  incidents.language stores the detected language.
- Assistant: fixed knowledge base (app/services/assistant_kb.py), keyword scoring, ties go to
  the topic listed first (most urgent first). Only 112 and 1363 appear as phone numbers.
  Answers are in English. Questions are not stored.
- Severity defaults per category (assumption): suspicious activity / other LOW; theft,
  accident, lost person, unknown MEDIUM; harassment, medical emergency, natural disaster HIGH;
  fire CRITICAL. The brief's keyword rules raise it from there (see app/services/severity.py).
- Risk zones in the demo are synthetic circles (ml/data/synthetic_risk_zones_jaipur.json).
- Risk model: unit = ~1 km grid cell x 6-hour bin (India time); grid cells are stored as
  risk_zones with kind "grid"; predictions in risk_predictions with the model_version.
  A zone's EFFECTIVE level = fixed base_level for hand-drawn zones, the latest prediction for
  the current bin for grid cells (LOW if none). Level thresholds 0.25 / 0.50 / 0.75 (brief).
- Risk features are shared code (backend/app/ml/risk_features.py) used by training and the
  API. The only history feature is each cell's training-period incident rate, stored in the
  model artefact. Weather at prediction time comes from the request or the fallback table.
- A tourist inside both a hand-drawn zone and a grid cell can get one alert for each.
- Staff see an incident's location only while the reporter's consent is on, or for an SOS.
- Digital tourist ID (Phase 9): a JWT with type "tourist_credential", signed with the same
  server secret, valid for 30 days (`CREDENTIAL_DAYS`, assumption). Claims: user id, name,
  nationality, issue and expiry time - no location. Verification also checks that the account
  is still an active tourist. No revocation list (limitation). QR codes are drawn by `segno`.
- Retention (Phase 9): `python -m app.cli purge-expired` deletes incident locations and clears
  tourists' latest locations whose expiry time has passed; incidents are kept without location.
  Each run is audited with the counts.
- Analytics (Phase 9): plain SQL counts for incidents created in the last N days (India time,
  1-90 days); "needs review" uses the same rule as the incident list.
- Security checks against the OWASP API Top 10 are listed in docs/security.md.
