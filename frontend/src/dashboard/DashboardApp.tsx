// Authority dashboard ("control room"), with three tabs:
//   Operations - active SOS banner, risk map, live geofence alerts, incident list with status
//                buttons, category / severity overrides and simulated dispatch
//   Analytics  - plain incident counts
//   Verify ID  - check a tourist's digital ID
// New incidents, status changes and geofence alerts arrive over the WebSocket without
// refreshing the page; the data is kept while switching tabs.

import { BarChart3, LayoutDashboard, LogOut, ScanLine } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { apiGet } from "../shared/api";
import { openLiveSocket } from "../shared/liveSocket";
import LoginForm from "../shared/LoginForm";
import { link } from "../shared/router";
import { setSession, useSession } from "../shared/session";
import type { Category, Incident, Session } from "../shared/types";
import { LiveIndicator, Notice } from "../shared/ui";
import AnalyticsPanel from "./AnalyticsPanel";
import CredentialCheck from "./CredentialCheck";
import OperationsView from "./OperationsView";
import type { GeofenceAlert } from "./OperationsView";

const TABS = [
  { id: "operations", label: "Operations", icon: LayoutDashboard },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "verify", label: "Verify ID", icon: ScanLine },
];

const ROLE_LABELS: Record<string, string> = {
  operator: "Operator",
  supervisor: "Supervisor",
  administrator: "Administrator",
};

export default function DashboardApp({ tab }: { tab?: string }) {
  const session = useSession("staff");
  if (session === null) {
    return <LoginForm initialKind="staff" />;
  }
  const current = TABS.some((t) => t.id === tab) ? tab! : "operations";
  return <ControlRoom session={session} tab={current} />;
}

// Put an incident into the list: replace it if we have it, otherwise add it at the top.
function upsert(list: Incident[], incident: Incident): Incident[] {
  const exists = list.some((i) => i.id === incident.id);
  return exists ? list.map((i) => (i.id === incident.id ? incident : i)) : [incident, ...list];
}

function ControlRoom({ session, tab }: { session: Session; tab: string }) {
  const { token } = session;
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [alerts, setAlerts] = useState<GeofenceAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState(0); // counts incident updates, to refresh analytics

  // Put a new or changed incident into the list, and let the analytics count again.
  const applyUpdate = useCallback((incident: Incident) => {
    setIncidents((list) => upsert(list, incident));
    setChanges((n) => n + 1);
  }, []);

  useEffect(() => {
    apiGet<Incident[]>("/incidents?limit=200", token)
      .then(setIncidents)
      .catch((err: Error) => setError(err.message));
    apiGet<Category[]>("/incident-categories", token)
      .then(setCategories)
      .catch((err: Error) => setError(err.message));
  }, [token]);

  useEffect(
    () =>
      openLiveSocket(
        "/ws/dashboard",
        token,
        (event) => {
          if (event.type === "geofence.alert") {
            setAlerts((list) => [event as GeofenceAlert, ...list].slice(0, 20));
          } else if ("incident" in event) {
            applyUpdate(event.incident as Incident);
          }
        },
        (status) => setConnected(status.connected),
      ),
    [token, applyUpdate],
  );

  function logOut() {
    setSession("staff", null);
    window.location.hash = link(); // back to the home page
  }

  return (
    <>
      <div className="app-header">
        <div>
          <h1>Control room</h1>
          <p>
            Signed in as {session.user.full_name}, {ROLE_LABELS[session.user.role] ?? session.user.role}
          </p>
        </div>
        <div className="row">
          <LiveIndicator connected={connected} />
          <button className="btn btn-secondary btn-sm" onClick={logOut}>
            <LogOut aria-hidden="true" />
            Log out
          </button>
        </div>
      </div>

      <nav className="tabs" aria-label="Dashboard">
        {TABS.map(({ id, label, icon: Icon }) => (
          <a key={id} href={link("dashboard", id)} aria-current={tab === id ? "page" : undefined}>
            <Icon aria-hidden="true" />
            {label}
          </a>
        ))}
      </nav>

      <div className="stack-lg">
        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}
        {tab === "analytics" && <AnalyticsPanel token={token} refreshKey={changes} />}
        {tab === "verify" && <CredentialCheck token={token} />}
        {tab === "operations" && (
          <OperationsView
            token={token}
            incidents={incidents}
            categories={categories}
            alerts={alerts}
            onIncidentChanged={applyUpdate}
          />
        )}
      </div>
    </>
  );
}
