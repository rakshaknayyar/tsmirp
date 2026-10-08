// Authority dashboard: map, live geofence alerts, live incident list, status buttons, and
// operator overrides of the automatic category / severity (every override is audited).
// New incidents, status changes and geofence alerts arrive over the WebSocket without
// refreshing the page.

import { Fragment, useCallback, useEffect, useState } from "react";

import { apiGet, apiRequest } from "../shared/api";
import { openLiveSocket } from "../shared/liveSocket";
import LoginForm from "../shared/LoginForm";
import SimulationNotice from "../shared/SimulationNotice";
import { SEVERITIES, STAFF_ROLES } from "../shared/types";
import type { Category, Incident, IncidentStatus, Session } from "../shared/types";
import DashboardMap from "./DashboardMap";
import ResourcePicker from "./ResourcePicker";

// Buttons offered for each status. Mirrors the backend lifecycle, except ASSIGNED, which is
// set by assigning a resource (the "Recommend resources" button).
const NEXT_STATUSES: Record<IncidentStatus, IncidentStatus[]> = {
  NEW: ["ACKNOWLEDGED"],
  ACKNOWLEDGED: ["RESOLVED"],
  ASSIGNED: ["EN_ROUTE", "RESOLVED"],
  EN_ROUTE: ["RESOLVED"],
  RESOLVED: ["CLOSED", "ACKNOWLEDGED"],
  CLOSED: [],
};

type GeofenceAlert = {
  type: "geofence.alert";
  tourist_user_id: number;
  zone: { id: number; name: string; level: string };
  at: string;
};

export default function DashboardApp() {
  const [session, setSession] = useState<Session | null>(null);

  if (session === null) {
    return (
      <>
        <SimulationNotice />
        <LoginForm title="Authority dashboard log in" onLoggedIn={setSession} />
      </>
    );
  }
  if (!STAFF_ROLES.includes(session.user.role)) {
    return <p>The dashboard is for operators, supervisors and administrators.</p>;
  }
  return <LiveIncidentList session={session} onLogout={() => setSession(null)} />;
}

// Put an incident into the list: replace it if we have it, otherwise add it at the top.
function upsert(list: Incident[], incident: Incident): Incident[] {
  const exists = list.some((i) => i.id === incident.id);
  return exists ? list.map((i) => (i.id === incident.id ? incident : i)) : [incident, ...list];
}

function LiveIncidentList({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [liveMode, setLiveMode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pickerFor, setPickerFor] = useState<number | null>(null); // incident id
  const [alerts, setAlerts] = useState<GeofenceAlert[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);

  useEffect(() => {
    apiGet<Incident[]>("/incidents", session.token)
      .then(setIncidents)
      .catch((err: Error) => setError(err.message));
    apiGet<Category[]>("/incident-categories", session.token)
      .then(setCategories)
      .catch((err: Error) => setError(err.message));
  }, [session.token]);

  useEffect(
    () =>
      openLiveSocket(
        "/ws/dashboard",
        session.token,
        (event) => {
          if (event.type === "geofence.alert") {
            setAlerts((list) => [event as GeofenceAlert, ...list].slice(0, 10));
          } else if ("incident" in event) {
            setIncidents((list) => upsert(list, event.incident as Incident));
          }
        },
        (status) => setLiveMode(status.mode),
      ),
    [session.token],
  );

  const changeStatus = useCallback(
    async (incident: Incident, status: IncidentStatus) => {
      setError(null);
      try {
        const updated = await apiRequest<Incident>("PATCH", `/incidents/${incident.id}/status`, {
          token: session.token,
          body: { status },
        });
        setIncidents((list) => upsert(list, updated));
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [session.token],
  );

  // Operator override of category and/or severity (PATCH /incidents/{id}).
  const override = useCallback(
    async (incident: Incident, change: { category_code?: string; severity?: string }) => {
      setError(null);
      try {
        const updated = await apiRequest<Incident>("PATCH", `/incidents/${incident.id}`, {
          token: session.token,
          body: change,
        });
        setIncidents((list) => upsert(list, updated));
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [session.token],
  );

  return (
    <>
      <SimulationNotice />
      <p>
        {session.user.full_name} ({session.user.role}) - live updates:{" "}
        <strong>{liveMode ? `connected (${liveMode})` : "disconnected, retrying"}</strong>{" "}
        <button onClick={onLogout}>Log out</button>
      </p>
      {error && <p role="alert">{error}</p>}

      <ActiveSosBanner incidents={incidents} />

      <DashboardMap token={session.token} incidents={incidents} />

      <h2>Geofence alerts (live)</h2>
      {alerts.length === 0 ? (
        <p>None since you logged in.</p>
      ) : (
        <ul>
          {alerts.map((a) => (
            <li key={`${a.at}-${a.tourist_user_id}-${a.zone.id}`}>
              {new Date(a.at).toLocaleTimeString()} - tourist #{a.tourist_user_id} has stayed in{" "}
              {a.zone.name} ({a.zone.level})
            </li>
          ))}
        </ul>
      )}

      <h2>Incidents</h2>
      {/* The table scrolls sideways inside this box on narrow screens, not the whole page. */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr style={{ textAlign: "left" }}>
              <th>#</th>
              <th>Reported</th>
              <th>Category</th>
              <th>Department</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Description</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((incident) => (
              <Fragment key={incident.id}>
                <tr style={{ borderTop: "1px solid #ddd" }}>
                  <td>{incident.id}</td>
                  <td>{new Date(incident.created_at).toLocaleString()}</td>
                  <td>
                    <select
                      aria-label={`Category of incident ${incident.id}`}
                      value={incident.category?.code ?? ""}
                      onChange={(e) => override(incident, { category_code: e.target.value })}
                    >
                      {!incident.category && <option value="">Uncategorised</option>}
                      {categories.map((c) => (
                        <option key={c.code} value={c.code}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    {incident.needs_review && (
                      <strong style={{ color: "#ef6c00" }} title="Check the category">
                        {" "}
                        needs review
                      </strong>
                    )}
                    {incident.confidence !== null && (
                      <div style={{ fontSize: 12 }}>
                        auto, confidence {Math.round(incident.confidence * 100)}%
                      </div>
                    )}
                  </td>
                  <td>{incident.category?.department ?? "-"}</td>
                  <td>
                    <select
                      aria-label={`Severity of incident ${incident.id}`}
                      value={incident.severity}
                      onChange={(e) => override(incident, { severity: e.target.value })}
                    >
                      {SEVERITIES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    {incident.is_sos && <strong style={{ color: "#c62828" }}> (SOS)</strong>}
                  </td>
                  <td>{incident.status}</td>
                  <td>{incident.description}</td>
                  <td>
                    {NEXT_STATUSES[incident.status].map((next) => (
                      <button key={next} onClick={() => changeStatus(incident, next)}>
                        {next}
                      </button>
                    ))}
                    {incident.status === "ACKNOWLEDGED" && incident.location && (
                      <button onClick={() => setPickerFor(incident.id)}>Recommend resources</button>
                    )}
                  </td>
                </tr>
                {pickerFor === incident.id && (
                  <tr>
                    <td colSpan={8}>
                      <ResourcePicker
                        incident={incident}
                        token={session.token}
                        onAssigned={(updated) => {
                          setIncidents((list) => upsert(list, updated));
                          setPickerFor(null);
                        }}
                        onClose={() => setPickerFor(null)}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {incidents.length === 0 && <p>No incidents yet.</p>}
    </>
  );
}

// Red banner listing every SOS that is still open, so it cannot be missed.
function ActiveSosBanner({ incidents }: { incidents: Incident[] }) {
  const open = incidents.filter(
    (i) => i.is_sos && i.status !== "RESOLVED" && i.status !== "CLOSED",
  );
  if (open.length === 0) return null;
  return (
    <div
      role="alert"
      style={{
        background: "#c62828",
        color: "#fff",
        padding: "8px 12px",
        borderRadius: 6,
        margin: "8px 0",
      }}
    >
      <strong>
        {open.length} active SOS{open.length > 1 ? " alerts" : ""}
      </strong>
      <ul style={{ margin: "4px 0" }}>
        {open.map((i) => (
          <li key={i.id}>
            SOS #{i.id} from tourist #{i.reporter_user_id} - {i.status} -{" "}
            {i.location
              ? `at ${i.location.lat.toFixed(5)}, ${i.location.lon.toFixed(5)}`
              : "location unknown"}{" "}
            - {new Date(i.created_at).toLocaleTimeString()}
          </li>
        ))}
      </ul>
      Acknowledge it below, then use "Recommend resources" to assign (simulated dispatch).
    </div>
  );
}
