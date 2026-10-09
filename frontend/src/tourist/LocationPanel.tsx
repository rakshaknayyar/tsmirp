// Location consent switch and location sharing, with the geofence result shown in plain words.
//
// "Demo position" lets you test the geofence from anywhere (e.g. during the viva) by sending a
// chosen Jaipur landmark instead of your real GPS position. It is clearly labelled as simulated.

import { LocateFixed } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { apiRequest } from "../shared/api";
import { formatDateTime } from "../shared/format";
import { LEVEL_LABELS } from "../shared/mapUtils";
import type { FixResult, Position, ZoneBrief } from "../shared/types";
import { Badge, Field, Notice, Panel, Switch } from "../shared/ui";

const DEMO_PLACES: Record<string, [number, number]> = {
  "Hawa Mahal": [26.9239, 75.8267],
  "Jaipur Junction station": [26.9196, 75.7878],
  "Amer Fort": [26.9855, 75.8513],
  "Albert Hall Museum": [26.9116, 75.8195],
};
const AUTO_SHARE_EVERY_MS = 30_000;

const LEVEL_TONES = { LOW: "success", MODERATE: "warning", HIGH: "danger", CRITICAL: "danger" } as const;

type Props = {
  token: string;
  consent: boolean;
  onConsentChange: (consent: boolean) => Promise<void>;
  onShared: (position: Position, result: FixResult) => void;
};

function ZoneBadges({ zones }: { zones: ZoneBrief[] }) {
  return (
    <span className="inline-badges">
      {zones.map((z) => (
        <Badge key={z.id} tone={LEVEL_TONES[z.level]}>
          {z.name}: {LEVEL_LABELS[z.level]}
        </Badge>
      ))}
    </span>
  );
}

export default function LocationPanel({ token, consent, onConsentChange, onShared }: Props) {
  const [result, setResult] = useState<FixResult | null>(null);
  const [sharedAt, setSharedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [autoShare, setAutoShare] = useState(false);
  const [demoPlace, setDemoPlace] = useState("");
  const lastSent = useRef(0);
  const id = useId();

  async function send(position: Position) {
    setError(null);
    try {
      const fix = await apiRequest<FixResult>("POST", "/tourist/location", {
        token,
        body: { lat: position.lat, lon: position.lon, accuracy_m: position.accuracy_m },
      });
      lastSent.current = Date.now();
      setResult(fix);
      setSharedAt(new Date().toISOString());
      onShared(position, fix);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLocating(false);
    }
  }

  function shareNow() {
    setLocating(true);
    if (demoPlace) {
      const [lat, lon] = DEMO_PLACES[demoPlace];
      void send({ lat, lon, accuracy_m: 15, simulated: true });
      return;
    }
    if (!navigator.geolocation) {
      setLocating(false);
      setError("This browser cannot provide a location. Choose a demo position instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) =>
        void send({
          lat: p.coords.latitude,
          lon: p.coords.longitude,
          accuracy_m: p.coords.accuracy,
          simulated: false,
        }),
      (err) => {
        setLocating(false);
        setError(`Could not get your location (${err.message}). Choose a demo position instead.`);
      },
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

  const inHighZone = result?.inside_zones.some((z) => z.level === "HIGH" || z.level === "CRITICAL");

  return (
    <Panel
      title="Location sharing"
      description="Only your latest position is kept, for 30 days at most. Staff can see it only while sharing is on, or during an SOS."
    >
      <div className="stack">
        <Switch
          checked={consent}
          onChange={(value) => void onConsentChange(value)}
          label="Share my location for safety alerts"
          description="Turning this off deletes your stored location straight away."
        />

        {consent && (
          <>
            <Field
              id={`${id}-source`}
              label="Where should your position come from?"
              hint="Demo positions are simulated GPS, for trying the app from anywhere."
            >
              <select
                id={`${id}-source`}
                className="select"
                value={demoPlace}
                onChange={(e) => setDemoPlace(e.target.value)}
              >
                <option value="">My real GPS position</option>
                {Object.keys(DEMO_PLACES).map((name) => (
                  <option key={name} value={name}>
                    Demo position: {name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="row">
              <button className="btn btn-primary" onClick={shareNow} disabled={locating}>
                <LocateFixed aria-hidden="true" />
                {locating ? "Finding your position…" : "Share my location now"}
              </button>
              <label className="check">
                <input
                  type="checkbox"
                  checked={autoShare}
                  onChange={(e) => setAutoShare(e.target.checked)}
                />
                <span>Keep sharing every 30 seconds while this page is open</span>
              </label>
            </div>
          </>
        )}

        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}
        {result && !result.accepted && (
          <Notice tone="warning" title="That position was not used">
            {result.reason}
          </Notice>
        )}
        {result?.accepted && (
          <Notice tone="info" live="status" title={`Location shared${sharedAt ? ` at ${formatDateTime(sharedAt)}` : ""}`}>
            <p>
              {result.inside_zones.length === 0 ? (
                "You are not inside any risk zone."
              ) : (
                <>
                  You are inside <ZoneBadges zones={result.inside_zones} />
                </>
              )}
            </p>
            {result.nearby_zones.length > 0 && (
              <p>
                Nearby: <ZoneBadges zones={result.nearby_zones} />
              </p>
            )}
          </Notice>
        )}
        {inHighZone && result?.alerts.length === 0 && (
          <Notice tone="warning">
            You are in a higher-risk area. If you stay for about a minute you will get an alert
            (the server waits a little to avoid false alarms).
          </Notice>
        )}
        {result?.alerts.map((alert) => (
          <Notice key={alert.id} tone="danger" live="alert" title={alert.title}>
            {alert.body}
          </Notice>
        ))}
      </div>
    </Panel>
  );
}
