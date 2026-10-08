// SOS button with a 5-second cancel window, then the SOS status (updated live) and an
// "I'm safe" button. Dispatch and SMS are SIMULATED by this prototype - the panel says so.

import { useEffect, useState } from "react";

import { apiRequest } from "../shared/api";
import { formatDistance } from "../shared/mapUtils";
import type { Incident, NearbyResource, Position, SosResponse } from "../shared/types";

const CANCEL_WINDOW_SECONDS = 5;

type Props = {
  token: string;
  position: Position | null; // last shared position (may be a demo position)
  incidents: Incident[];
  onChanged: () => void;
};

// Get a location for the SOS: a demo position if one is in use, otherwise real GPS
// (waiting at most 4 s), otherwise the last shared position, otherwise none.
function locateForSos(position: Position | null): Promise<Position | null> {
  if (position?.simulated || !navigator.geolocation) return Promise.resolve(position);
  return new Promise((resolve) =>
    navigator.geolocation.getCurrentPosition(
      (p) =>
        resolve({
          lat: p.coords.latitude,
          lon: p.coords.longitude,
          accuracy_m: p.coords.accuracy,
          simulated: false,
        }),
      () => resolve(position),
      { enableHighAccuracy: true, timeout: 4_000 },
    ),
  );
}

export default function SosPanel({ token, position, incidents, onChanged }: Props) {
  const [countdown, setCountdown] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [lastResponse, setLastResponse] = useState<SosResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeSos = incidents.find(
    (i) => i.is_sos && i.status !== "RESOLVED" && i.status !== "CLOSED",
  );

  // The cancel window: count down once per second, send when it reaches zero.
  useEffect(() => {
    if (countdown === null) return;
    if (countdown === 0) {
      setCountdown(null);
      void sendSos();
      return;
    }
    const timer = window.setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => window.clearTimeout(timer);
  });

  async function sendSos() {
    setSending(true);
    setError(null);
    try {
      const where = await locateForSos(position);
      const response = await apiRequest<SosResponse>("POST", "/sos", {
        token,
        body: {
          location: where
            ? { lat: where.lat, lon: where.lon, accuracy_m: where.accuracy_m }
            : null,
        },
      });
      setLastResponse(response);
      onChanged();
    } catch (err) {
      setError(`${(err as Error).message} - please call 112 directly.`);
    } finally {
      setSending(false);
    }
  }

  async function imSafe(incident: Incident) {
    setError(null);
    try {
      await apiRequest<SosResponse>("POST", `/sos/${incident.id}/cancel`, { token });
      setLastResponse(null);
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const help: NearbyResource[] =
    lastResponse && activeSos && lastResponse.incident.id === activeSos.id
      ? lastResponse.nearest_help
      : [];

  return (
    <section
      style={{ border: "2px solid #c62828", borderRadius: 6, padding: 12, margin: "12px 0" }}
    >
      <h2 style={{ marginTop: 0, color: "#c62828" }}>Emergency</h2>
      <p style={{ fontSize: 13 }}>
        This prototype only <strong>simulates</strong> dispatch and SMS. If you are in danger,{" "}
        <strong>call 112</strong> first. Tourist helpline: 1363.
      </p>

      {!activeSos && countdown === null && !sending && (
        <button
          onClick={() => setCountdown(CANCEL_WINDOW_SECONDS)}
          style={{
            background: "#c62828",
            color: "#fff",
            fontSize: 22,
            fontWeight: "bold",
            padding: "14px 32px",
            borderRadius: 40,
            border: "none",
          }}
        >
          SOS
        </button>
      )}

      {countdown !== null && (
        <p role="alert">
          Sending SOS in <strong>{countdown}</strong> s - your location will be shared for this
          emergency.{" "}
          <button onClick={() => setCountdown(null)}>Cancel</button>
        </p>
      )}
      {sending && <p>Sending SOS...</p>}

      {activeSos && (
        <div role="status">
          <p>
            <strong>SOS #{activeSos.id} is active</strong> - status:{" "}
            <strong>{activeSos.status}</strong> (updates appear here automatically).
          </p>
          {lastResponse?.created && lastResponse.incident.id === activeSos.id && (
            <p style={{ fontSize: 13 }}>
              {lastResponse.contacts_notified} emergency contact(s) notified by simulated SMS.
              {activeSos.location ? "" : " Your location could not be attached."}
            </p>
          )}
          {help.length > 0 && (
            <>
              <p style={{ marginBottom: 4 }}>Nearest help (straight-line distance):</p>
              <ul style={{ marginTop: 0 }}>
                {help.map((r) => (
                  <li key={r.id}>
                    {r.resource_type === "hospital" ? "Hospital" : "Police"}: {r.name} -{" "}
                    {formatDistance(r.distance_m)}
                  </li>
                ))}
              </ul>
            </>
          )}
          <button onClick={() => imSafe(activeSos)}>I'm safe - cancel my SOS</button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
