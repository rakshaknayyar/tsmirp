// The Operations tab: open SOS alerts first, then the map with the risk-model button, the live
// geofence alerts, and the incident list.

import { MapPinned, RadioTower, Siren, Sparkles } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../shared/api";
import { formatDateTime, STATUS_LABELS } from "../shared/format";
import type { Category, Incident } from "../shared/types";
import { EmptyState, Notice, Panel } from "../shared/ui";
import DashboardMap from "./DashboardMap";
import IncidentsTable from "./IncidentsTable";

export type GeofenceAlert = {
  type: "geofence.alert";
  tourist_user_id: number;
  zone: { id: number; name: string; level: string };
  at: string;
};

type Props = {
  token: string;
  incidents: Incident[];
  categories: Category[];
  alerts: GeofenceAlert[];
  onIncidentChanged: (incident: Incident) => void;
};

// Red banner listing every SOS that is still open, so it cannot be missed.
function ActiveSosBanner({ incidents }: { incidents: Incident[] }) {
  const open = incidents.filter(
    (i) => i.is_sos && i.status !== "RESOLVED" && i.status !== "CLOSED",
  );
  if (open.length === 0) return null;
  return (
    <section className="sos-banner" role="alert" aria-labelledby="sos-banner-title">
      <Siren aria-hidden="true" />
      <div>
        <h2 id="sos-banner-title">
          {open.length === 1 ? "1 active SOS" : `${open.length} active SOS alerts`}
        </h2>
        <ul>
          {open.map((i) => (
            <li key={i.id}>
              SOS #{i.id} from tourist #{i.reporter_user_id}, {STATUS_LABELS[i.status].toLowerCase()},{" "}
              {i.location
                ? `at ${i.location.lat.toFixed(5)}, ${i.location.lon.toFixed(5)}`
                : "location unknown"}
              , {formatDateTime(i.created_at)}
            </li>
          ))}
        </ul>
        <p>Acknowledge it in the list below, then use "Recommend units" to assign one (simulated dispatch).</p>
      </div>
    </section>
  );
}

export default function OperationsView({
  token,
  incidents,
  categories,
  alerts,
  onIncidentChanged,
}: Props) {
  const [zonesVersion, setZonesVersion] = useState(0);
  const [riskMessage, setRiskMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const [computing, setComputing] = useState(false);

  // Run the risk model for today (POST /risk/predict) and redraw the map.
  async function computeRisk() {
    setComputing(true);
    setRiskMessage(null);
    try {
      const result = await apiRequest<{
        model_version: string;
        rows_written: number;
        by_level: Record<string, number>;
        weather_source: string;
      }>("POST", "/risk/predict", { token, body: {} });
      const levels = Object.entries(result.by_level)
        .map(([level, n]) => `${level.toLowerCase()} ${n}`)
        .join(", ");
      setRiskMessage({
        tone: "success",
        text:
          `${result.rows_written} cell-periods scored by ${result.model_version} (weather: ` +
          `${result.weather_source}): ${levels}. Relative estimates from a model trained on synthetic data.`,
      });
      setZonesVersion((v) => v + 1);
    } catch (err) {
      setRiskMessage({ tone: "danger", text: (err as Error).message });
    } finally {
      setComputing(false);
    }
  }

  return (
    <>
      <ActiveSosBanner incidents={incidents} />

      <div className="ops-grid">
        <Panel
          title="Live map"
          description="Risk zones for the current 6-hour period and every incident whose location you may see (consent or SOS)."
          actions={
            <button className="btn btn-secondary btn-sm" onClick={() => void computeRisk()} disabled={computing}>
              <Sparkles aria-hidden="true" />
              {computing ? "Computing…" : "Compute today's risk levels"}
            </button>
          }
        >
          <div className="stack">
            {riskMessage && (
              <Notice tone={riskMessage.tone} live="status">
                {riskMessage.text}
              </Notice>
            )}
            <DashboardMap token={token} incidents={incidents} zonesVersion={zonesVersion} />
          </div>
        </Panel>

        <Panel title="Geofence alerts" description="Tourists who stayed in a high-risk area, since you logged in.">
          {alerts.length === 0 ? (
            <EmptyState icon={<RadioTower aria-hidden="true" />} title="All quiet">
              New alerts appear here instantly.
            </EmptyState>
          ) : (
            <ul className="list">
              {alerts.map((a) => (
                <li className="list-item" key={`${a.at}-${a.tourist_user_id}-${a.zone.id}`}>
                  <span className="list-item-icon">
                    <MapPinned aria-hidden="true" />
                  </span>
                  <span className="list-item-main">
                    <span className="list-item-title">Tourist #{a.tourist_user_id}</span>
                    <span className="list-item-sub">
                      In {a.zone.name} ({a.zone.level.toLowerCase()}), {formatDateTime(a.at)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <IncidentsTable
        token={token}
        incidents={incidents}
        categories={categories}
        onIncidentChanged={onIncidentChanged}
      />
    </>
  );
}
