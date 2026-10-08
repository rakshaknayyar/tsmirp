// Authority dashboard (bare Phase 2 version): live incident list + status buttons.
// New incidents and status changes arrive over the WebSocket without refreshing the page.

import { useCallback, useEffect, useState } from "react";

import { apiGet, apiRequest, dashboardSocketUrl } from "../shared/api";
import LoginForm from "../shared/LoginForm";
import SimulationNotice from "../shared/SimulationNotice";
import { STAFF_ROLES } from "../shared/types";
import type { Incident, IncidentStatus, Session } from "../shared/types";

// Buttons offered for each status. Mirrors the backend lifecycle, except ASSIGNED, which is
// set by assigning a resource (Phase 3).
const NEXT_STATUSES: Record<IncidentStatus, IncidentStatus[]> = {
  NEW: ["ACKNOWLEDGED"],
  ACKNOWLEDGED: ["RESOLVED"],
  ASSIGNED: ["EN_ROUTE", "RESOLVED"],
  EN_ROUTE: ["RESOLVED"],
  RESOLVED: ["CLOSED", "ACKNOWLEDGED"],
  CLOSED: [],
};

type LiveEvent =
  | { type: "ready"; mode: string }
  | { type: "incident.created" | "incident.status_changed"; incident: Incident };

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

  useEffect(() => {
    apiGet<Incident[]>("/incidents", session.token)
      .then(setIncidents)
      .catch((err: Error) => setError(err.message));
  }, [session.token]);

  useEffect(() => {
    let socket: WebSocket;
    let retryTimer: number | undefined;
    let stopped = false;

    function connect() {
      socket = new WebSocket(dashboardSocketUrl());
      // The token goes in the first message, not in the URL.
      socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token: session.token }));
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as LiveEvent;
        if (event.type === "ready") setLiveMode(event.mode);
        else setIncidents((list) => upsert(list, event.incident));
      };
      socket.onclose = () => {
        setLiveMode(null);
        if (!stopped) retryTimer = window.setTimeout(connect, 3000); // try again shortly
      };
    }

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      socket.close();
    };
  }, [session.token]);

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

  return (
    <>
      <SimulationNotice />
      <p>
        {session.user.full_name} ({session.user.role}) - live updates:{" "}
        <strong>{liveMode ? `connected (${liveMode})` : "disconnected, retrying"}</strong>{" "}
        <button onClick={onLogout}>Log out</button>
      </p>
      {error && <p role="alert">{error}</p>}

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
            <tr key={incident.id} style={{ borderTop: "1px solid #ddd" }}>
              <td>{incident.id}</td>
              <td>{new Date(incident.created_at).toLocaleString()}</td>
              <td>{incident.category?.name ?? "Uncategorised"}</td>
              <td>{incident.category?.department ?? "-"}</td>
              <td>{incident.severity}</td>
              <td>{incident.status}</td>
              <td>{incident.description}</td>
              <td>
                {NEXT_STATUSES[incident.status].map((next) => (
                  <button key={next} onClick={() => changeStatus(incident, next)}>
                    {next}
                  </button>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {incidents.length === 0 && <p>No incidents yet.</p>}
    </>
  );
}
