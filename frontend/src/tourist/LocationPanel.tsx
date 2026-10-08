// Location consent switch + location sharing, with the geofence result shown to the tourist.
//
// "Demo position" lets you test the geofence from anywhere (e.g. during the viva) by sending
// a chosen Jaipur landmark instead of your real GPS position. It is clearly labelled.

import { useEffect, useRef, useState } from "react";

import { apiRequest } from "../shared/api";
import type { FixResult, Position } from "../shared/types";

const DEMO_PLACES: Record<string, [number, number]> = {
  "Hawa Mahal": [26.9239, 75.8267],
  "Jaipur Junction station": [26.9196, 75.7878],
  "Amer Fort": [26.9855, 75.8513],
  "Albert Hall Museum": [26.9116, 75.8195],
};
const AUTO_SHARE_EVERY_MS = 30_000;

type Props = {
  token: string;
  consent: boolean;
  onConsentChange: (consent: boolean) => Promise<void>;
  onShared: (position: Position, result: FixResult) => void;
};

export default function LocationPanel({ token, consent, onConsentChange, onShared }: Props) {
  const [result, setResult] = useState<FixResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoShare, setAutoShare] = useState(false);
  const [demoPlace, setDemoPlace] = useState("");
  const lastSent = useRef(0);

  async function send(position: Position) {
    setError(null);
    try {
      const fix = await apiRequest<FixResult>("POST", "/tourist/location", {
        token,
        body: { lat: position.lat, lon: position.lon, accuracy_m: position.accuracy_m },
      });
      lastSent.current = Date.now();
      setResult(fix);
      onShared(position, fix);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function shareNow() {
    if (demoPlace) {
      const [lat, lon] = DEMO_PLACES[demoPlace];
      send({ lat, lon, accuracy_m: 15, simulated: true });
      return;
    }
    if (!navigator.geolocation) {
      setError("This browser cannot provide a location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) =>
        send({
          lat: p.coords.latitude,
          lon: p.coords.longitude,
          accuracy_m: p.coords.accuracy,
          simulated: false,
        }),
      (err) => setError(`Could not get your location: ${err.message}`),
      { enableHighAccuracy: true, timeout: 15_000 },
    );
  }

  // Keep sharing every 30 s while the switch is on, consent is given and the page is open.
  useEffect(() => {
    if (!autoShare || !consent) return;
    const timer = window.setInterval(() => {
      if (Date.now() - lastSent.current >= AUTO_SHARE_EVERY_MS) shareNow();
    }, 5_000);
    return () => window.clearInterval(timer);
  });

  return (
    <section style={{ border: "1px solid #999", borderRadius: 6, padding: 12, margin: "12px 0" }}>
      <h2 style={{ marginTop: 0 }}>Location sharing</h2>
      <label>
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => onConsentChange(e.target.checked)}
        />{" "}
        I agree to share my location with TSMIRP for safety alerts.
      </label>
      <p style={{ fontSize: 13 }}>
        Only your latest position is kept (for 30 days at most). Authorities can see it only while
        this is switched on, or during an SOS. Switching it off deletes your stored location
        immediately.
      </p>

      {consent && (
        <>
          <label>
            Position source:{" "}
            <select value={demoPlace} onChange={(e) => setDemoPlace(e.target.value)}>
              <option value="">My real GPS position</option>
              {Object.keys(DEMO_PLACES).map((name) => (
                <option key={name} value={name}>
                  Demo position (simulated GPS): {name}
                </option>
              ))}
            </select>
          </label>{" "}
          <button onClick={shareNow}>Share my location now</button>{" "}
          <label>
            <input
              type="checkbox"
              checked={autoShare}
              onChange={(e) => setAutoShare(e.target.checked)}
            />{" "}
            Keep sharing every 30 s while this page is open
          </label>
        </>
      )}

      {error && <p role="alert">{error}</p>}
      {result && !result.accepted && <p>Not used: {result.reason}</p>}
      {result?.accepted && (
        <div>
          <p>
            Inside:{" "}
            {result.inside_zones.length === 0
              ? "no risk zone"
              : result.inside_zones.map((z) => `${z.name} (${z.level})`).join(", ")}
            . Nearby:{" "}
            {result.nearby_zones.length === 0
              ? "none"
              : result.nearby_zones.map((z) => `${z.name} (${z.level})`).join(", ")}
            .
          </p>
          {result.inside_zones.some((z) => z.level === "HIGH" || z.level === "CRITICAL") &&
            result.alerts.length === 0 && (
              <p style={{ fontSize: 13 }}>
                You are inside a higher-risk zone. An alert appears if you stay for about a
                minute (the server waits to avoid false alarms).
              </p>
            )}
          {result.alerts.map((alert) => (
            <p
              key={alert.id}
              role="alert"
              style={{ background: "#fde0dc", color: "#5f1d14", padding: 8, borderRadius: 6 }}
            >
              <strong>{alert.title}</strong>
              <br />
              {alert.body}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
