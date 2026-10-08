# Security checks: OWASP API Security Top 10 (2023)

How each risk is handled in TSMIRP and which automated tests check it (all in
`backend/tests/`, run with `pytest`). This is a prototype: the checks below are tests written
by the author, not an independent penetration test.

| # | Risk | What TSMIRP does | Tests |
|---|---|---|---|
| API1 | Broken object level authorisation | Every tourist query is filtered by the logged-in user; another user's object gives 404. Staff see a location only with consent or during an active SOS | `test_incidents.py::test_tourists_only_see_their_own_incidents`, `test_tourist.py::test_tourist_cannot_see_or_delete_another_tourists_contact`, `test_geofence.py::test_tourist_cannot_view_other_locations`, `test_geofence.py::test_notifications_are_private`, `test_sos.py::test_cancel_only_own_open_sos`, `test_sos.py::test_tourist_socket_gets_only_own_incident_updates` |
| API2 | Broken authentication | Argon2id hashes; short-lived JWT access tokens; a "type" claim so refresh tokens and QR credentials cannot be used to log in; login rate limit; same answer for a wrong password and an unknown e-mail | `test_security.py::test_every_endpoint_requires_login` (every documented endpoint), `test_security.py::test_expired_and_unsigned_tokens_are_rejected`, `test_auth.py` (token types, forged tokens, rate limit), `test_credential.py::test_login_token_is_not_a_credential_and_credential_cannot_log_in` |
| API3 | Broken object property level authorisation | Request models reject unknown fields (`extra="forbid"`), so a client cannot set role, severity, status or consent through the wrong endpoint; responses never include password hashes | `test_security.py::test_unknown_fields_are_rejected_not_ignored`, `test_security.py::test_password_hash_is_never_returned`, `test_auth.py::test_register_cannot_choose_a_role`, `test_incidents.py::test_tourist_cannot_set_severity_or_status`, `test_tourist.py::test_profile_update_cannot_change_consent` |
| API4 | Unrestricted resource consumption | Rate limits on login, SOS and classification; maximum text lengths; page size at most 200; map box at most ~5 x 5 degrees; analytics at most 90 days | `test_security.py::test_sizes_and_page_lengths_are_limited`, `test_auth.py::test_login_is_rate_limited`, `test_sos.py::test_sos_is_rate_limited`, `test_classification.py::test_classify_needs_login_and_is_rate_limited`, `test_analytics.py::test_summary_rules`, `test_assistant.py::test_endpoint_rules` |
| API5 | Broken function level authorisation | Role checks as FastAPI dependencies on every route; staff-only and admin-only functions | `test_security.py::test_tourists_cannot_call_staff_functions`, `test_rbac.py`, `test_sos.py::test_staff_cannot_trigger_sos`, `test_sos.py::test_staff_cannot_use_tourist_socket`, `test_credential.py::test_credential_roles` |
| API6 | Unrestricted access to sensitive business flows | SOS: rate limit and an open SOS is returned instead of a duplicate; staff accounts can only be created by an administrator | `test_sos.py::test_sos_is_rate_limited`, `test_sos.py::test_second_sos_returns_the_open_one`, `test_rbac.py::test_role_access` (`/admin/users`) |
| API7 | Server-side request forgery | The server only calls fixed addresses written in the code (Overpass mirrors, Open-Meteo), from CLI/training scripts; no request field takes a URL | `test_security.py::test_no_endpoint_accepts_a_url_from_the_user` |
| API8 | Security misconfiguration | No CORS (the frontend is served through the same origin); plain error messages without stack traces; the API refuses to start without a JWT secret of at least 32 characters; secrets only in `.env` (git-ignored) | `test_security.py::test_no_cross_origin_access_and_plain_errors` |
| API9 | Improper inventory management | One documented API (OpenAPI at `/docs`), listed in the README; the login test runs over this inventory, so a new endpoint is checked automatically | `test_security.py::test_every_endpoint_requires_login`, `test_security.py::test_public_endpoints_exist_and_the_inventory_is_complete` |
| API10 | Unsafe consumption of APIs | Data from Overpass and Open-Meteo is validated before use: elements without coordinates are dropped, missing weather values are filled from a table, and a failed weather download falls back to that table instead of crashing | `test_osm_import.py::test_parse_keeps_only_resources_with_coordinates`, `test_risk_model.py` (fallback weather) |

## Other protections
- Hash-chained audit log; editing or deleting a row is detected (`test_audit.py`), and it
  never contains passwords (`test_audit.py::test_audit_log_never_contains_passwords`).
- The digital tourist ID is signed; altered or expired credentials are rejected
  (`test_credential.py`).

## Not covered
- No load test or denial-of-service test was carried out.
- Rate limits are kept in memory per API process; several processes would each have their own
  counters (a shared store such as Redis would be needed).
- No HTTPS in local development; a real deployment would run behind a TLS proxy.
