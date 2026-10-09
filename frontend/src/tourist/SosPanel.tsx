// SOS button with a 5-second cancel window (shown as a shrinking ring), then the SOS progress
// (updated live) and an "I'm safe" button. Dispatch and SMS are SIMULATED by this prototype,
// and the card says so.

import { Hospital, Phone, ShieldHalf } from "lucide-react";
import { useEffect, useState } from "react";

import { apiRequest } from "../shared/api";
import { formatDistance } from "../shared/mapUtils";
import { link } from "../shared/router";
import type { Incident, IncidentStatus, NearbyResource, Position, SosResponse } from "../shared/types";
import { Notice } from "../shared/ui";

const CANCEL_WINDOW_SECONDS = 5;
const RING_RADIUS = 68;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

const STEPS: { status: IncidentStatus; label: string }[] = [
  { status: "NEW", label: "Sent" },
  { status: "ACKNOWLEDGED", label: "Seen by operator" },
  { status: "ASSIGNED", label: "Unit assigned" },
  { status: "EN_ROUTE", label: "On the way" },
  { status: "RESOLVED", label: "Resolved" },
];

type Props = {
  token: string;
  position: Position | null; // last shared position (may be a demo position)
  incidents: Incident[];
  contactCount: number;
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

export default function SosPanel({ token, position, incidents, contactCount, onChanged }: Props) {
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
      setError(`${(err as Error).message} Please call 112 directly.`);
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

  const errorNotice = error && (
    <Notice tone="danger" live="alert">
      {error}
    </Notice>
  );

  // ----- an SOS is open: show its progress -----
  if (activeSos) {
    const current = STEPS.findIndex((s) => s.status === activeSos.status);
    const help: NearbyResource[] =
      lastResponse && lastResponse.incident.id === activeSos.id ? lastResponse.nearest_help : [];
    return (
      <section className="sos-card" data-state="active" aria-labelledby="sos-title" role="status">
        <div className="stack">
          <div>
            <h2 id="sos-title">Your SOS is active</h2>
            <p>
              The control room has your alert (SOS #{activeSos.id}). This page updates by itself.
              If you are in danger, also call 112.
            </p>
          </div>
          <ol className="tracker" aria-label="SOS progress">
            {STEPS.map((step, index) => (
              <li
                key={step.status}
                data-done={index < current || index === current}
                aria-current={index === current ? "step" : undefined}
              >
                {step.label}
              </li>
            ))}
          </ol>
          {lastResponse?.created && lastResponse.incident.id === activeSos.id && (
            <p className="small muted">
              {lastResponse.contacts_notified === 0
                ? "You have no emergency contacts, so nobody was messaged."
                : `${lastResponse.contacts_notified} emergency contact(s) were sent a simulated SMS.`}
              {activeSos.location ? "" : " Your location could not be attached."}
            </p>
          )}
          {help.length > 0 && (
            <div className="stack">
              <h3>Nearest help (straight-line distance)</h3>
              <ul className="list">
                {help.map((r) => (
                  <li className="list-item" key={r.id}>
                    <span className="list-item-icon">
                      {r.resource_type === "hospital" ? (
                        <Hospital aria-hidden="true" />
                      ) : (
                        <ShieldHalf aria-hidden="true" />
                      )}
                    </span>
                    <span className="list-item-main">
                      <span className="list-item-title">{r.name}</span>
                      <span className="list-item-sub">
                        {r.resource_type === "hospital" ? "Hospital" : "Police"},{" "}
                        {formatDistance(r.distance_m)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="row">
            <button className="btn btn-secondary" onClick={() => imSafe(activeSos)}>
              I'm safe, cancel my SOS
            </button>
            <a className="btn btn-danger" href="tel:112">
              <Phone aria-hidden="true" />
              Call 112
            </a>
          </div>
          {errorNotice}
        </div>
      </section>
    );
  }

  // ----- counting down: the tourist can still cancel -----
  if (countdown !== null) {
    const offset = RING_LENGTH * (1 - countdown / CANCEL_WINDOW_SECONDS);
    return (
      <section className="sos-card" aria-labelledby="sos-title">
        <div className="sos-countdown" aria-hidden="true">
          <svg viewBox="0 0 152 152">
            <circle className="sos-ring-track" cx="76" cy="76" r={RING_RADIUS} strokeWidth="10" />
            <circle
              className="sos-ring-progress"
              cx="76"
              cy="76"
              r={RING_RADIUS}
              strokeWidth="10"
              strokeDasharray={RING_LENGTH}
              strokeDashoffset={offset}
            />
          </svg>
          <span className="sos-countdown-number">{countdown}</span>
        </div>
        <div className="stack">
          <div role="alert">
            <h2 id="sos-title">Sending SOS in {countdown} seconds</h2>
            <p>Your location will be shared with the control room for this emergency.</p>
          </div>
          <div className="row">
            <button className="btn btn-secondary" onClick={() => setCountdown(null)} autoFocus>
              Cancel, I'm fine
            </button>
          </div>
        </div>
      </section>
    );
  }

  // ----- ready -----
  return (
    <section className="sos-card" aria-labelledby="sos-title">
      <button
        className="sos-button"
        onClick={() => setCountdown(CANCEL_WINDOW_SECONDS)}
        disabled={sending}
        aria-describedby="sos-help"
      >
        <span className="sos-button-label">SOS</span>
        <span className="sos-button-hint">{sending ? "Sending…" : "Press for help"}</span>
      </button>
      <div className="stack">
        <div>
          <h2 id="sos-title">Need help now?</h2>
          <p id="sos-help">
            Press SOS to alert the control room. You get {CANCEL_WINDOW_SECONDS} seconds to cancel
            if you pressed it by mistake. This prototype only simulates dispatch, so if you are in
            danger, call 112 first.
          </p>
        </div>
        <div className="row">
          <a className="btn btn-secondary btn-sm" href="tel:112">
            <Phone aria-hidden="true" />
            Call 112
          </a>
          <a className="btn btn-ghost btn-sm" href="tel:1363">
            Tourist helpline 1363
          </a>
        </div>
        {contactCount === 0 && (
          <Notice tone="info">
            Add an emergency contact so someone you trust is told when you press SOS.{" "}
            <a href={link("tourist", "profile")}>Add a contact</a>
          </Notice>
        )}
        {errorNotice}
      </div>
    </section>
  );
}
