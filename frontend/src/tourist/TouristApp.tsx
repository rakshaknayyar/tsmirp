// Tourist app (bare Phase 2 version): log in, report an incident, see my incidents.
// Location sharing, the map and SOS are added in Phases 4 and 5.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { apiGet, apiRequest } from "../shared/api";
import LoginForm from "../shared/LoginForm";
import SimulationNotice from "../shared/SimulationNotice";
import type { Category, Incident, Session } from "../shared/types";

export default function TouristApp() {
  const [session, setSession] = useState<Session | null>(null);

  if (session === null) {
    return (
      <>
        <SimulationNotice />
        <LoginForm title="Tourist log in" allowRegister onLoggedIn={setSession} />
      </>
    );
  }
  if (session.user.role !== "tourist") {
    return <p>This page is for tourists. Staff should use the authority dashboard.</p>;
  }
  return <ReportAndList session={session} onLogout={() => setSession(null)} />;
}

function ReportAndList({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [description, setDescription] = useState("");
  const [categoryCode, setCategoryCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const loadIncidents = useCallback(() => {
    apiGet<Incident[]>("/incidents", session.token)
      .then(setIncidents)
      .catch((err: Error) => setMessage(err.message));
  }, [session.token]);

  useEffect(() => {
    apiGet<Category[]>("/incident-categories", session.token)
      .then(setCategories)
      .catch((err: Error) => setMessage(err.message));
    loadIncidents();
  }, [session.token, loadIncidents]);

  async function handleReport(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    try {
      await apiRequest<Incident>("POST", "/incidents", {
        token: session.token,
        body: { description, category_code: categoryCode || null },
      });
      setDescription("");
      setCategoryCode("");
      setMessage("Report sent. An operator will see it on the dashboard.");
      loadIncidents();
    } catch (err) {
      setMessage((err as Error).message);
    }
  }

  return (
    <>
      <SimulationNotice />
      <p>
        Logged in as {session.user.full_name} <button onClick={onLogout}>Log out</button>
      </p>

      <h2>Report an incident</h2>
      <form onSubmit={handleReport} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
        <select value={categoryCode} onChange={(e) => setCategoryCode(e.target.value)}>
          <option value="">Category (optional - not sure)</option>
          {categories.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
        <textarea
          placeholder="What happened? (at least 5 characters)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          minLength={5}
          maxLength={2000}
          rows={4}
          required
        />
        <button type="submit">Send report</button>
      </form>
      {message && <p role="status">{message}</p>}

      <h2>My incidents</h2>
      {incidents.length === 0 ? (
        <p>No reports yet.</p>
      ) : (
        <ul>
          {incidents.map((incident) => (
            <li key={incident.id}>
              #{incident.id} {incident.category?.name ?? "Uncategorised"} - {incident.status} -{" "}
              {incident.description}
            </li>
          ))}
        </ul>
      )}
      <button onClick={loadIncidents}>Refresh</button>
    </>
  );
}
