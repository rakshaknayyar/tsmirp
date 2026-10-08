// Tourist app: log in, location consent + sharing with geofence alerts, map with risk zones
// and nearby help, incident reports, my incidents and my notifications.
// SOS is added in Phase 5.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { apiGet, apiRequest } from "../shared/api";
import LoginForm from "../shared/LoginForm";
import SimulationNotice from "../shared/SimulationNotice";
import type {
  AppNotification,
  Category,
  FixResult,
  Incident,
  Position,
  Profile,
  Session,
} from "../shared/types";
import LocationPanel from "./LocationPanel";
import TouristMap from "./TouristMap";

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
  return <TouristHome session={session} onLogout={() => setSession(null)} />;
}

function TouristHome({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const { token } = session;
  const [profile, setProfile] = useState<Profile | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [description, setDescription] = useState("");
  const [categoryCode, setCategoryCode] = useState("");
  const [attachLocation, setAttachLocation] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const showError = (err: Error) => setMessage(err.message);

  const loadLists = useCallback(() => {
    apiGet<Incident[]>("/incidents", token).then(setIncidents).catch(showError);
    apiGet<AppNotification[]>("/tourist/notifications", token)
      .then(setNotifications)
      .catch(showError);
  }, [token]);

  useEffect(() => {
    apiGet<Profile>("/tourist/profile", token).then(setProfile).catch(showError);
    apiGet<Category[]>("/incident-categories", token).then(setCategories).catch(showError);
    loadLists();
  }, [token, loadLists]);

  async function changeConsent(consent: boolean) {
    try {
      const updated = await apiRequest<Profile>("PUT", "/tourist/consent", {
        token,
        body: { location_consent: consent },
      });
      setProfile(updated);
      if (!consent) {
        setPosition(null); // the server has deleted the stored location
        setAttachLocation(false);
      }
    } catch (err) {
      showError(err as Error);
    }
  }

  function handleShared(newPosition: Position, result: FixResult) {
    if (result.accepted) setPosition(newPosition);
    if (result.alerts.length > 0) loadLists();
  }

  async function handleReport(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    const location =
      attachLocation && position
        ? { lat: position.lat, lon: position.lon, accuracy_m: position.accuracy_m }
        : null;
    try {
      await apiRequest<Incident>("POST", "/incidents", {
        token,
        body: { description, category_code: categoryCode || null, location },
      });
      setDescription("");
      setCategoryCode("");
      setMessage("Report sent. An operator will see it on the dashboard.");
      loadLists();
    } catch (err) {
      showError(err as Error);
    }
  }

  const consent = profile?.location_consent ?? false;

  return (
    <>
      <SimulationNotice />
      <p>
        Logged in as {session.user.full_name} <button onClick={onLogout}>Log out</button>
      </p>

      <LocationPanel
        token={token}
        consent={consent}
        onConsentChange={changeConsent}
        onShared={handleShared}
      />
      <TouristMap token={token} position={position} />

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
        <label>
          <input
            type="checkbox"
            checked={attachLocation}
            disabled={!consent || position === null}
            onChange={(e) => setAttachLocation(e.target.checked)}
          />{" "}
          Attach my last shared location
          {(!consent || position === null) && " (share your location first)"}
        </label>
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

      <h2>My notifications</h2>
      {notifications.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {notifications.map((n) => (
            <li key={n.id}>
              {new Date(n.created_at).toLocaleString()} - <strong>{n.title}</strong>: {n.body}
            </li>
          ))}
        </ul>
      )}
      <button onClick={loadLists}>Refresh</button>
    </>
  );
}
