// Dashboard map: risk zones and every incident whose location the operator may see
// (consent or SOS rules are applied by the API; incidents without a location are not drawn).

import { CircleMarker } from "react-leaflet";

import { SEVERITY_LABELS, STATUS_LABELS } from "../shared/format";
import MapLegend from "../shared/MapLegend";
import MapView from "../shared/MapView";
import { popupContent, SEVERITY_COLOURS } from "../shared/mapUtils";
import RiskZonesLayer from "../shared/RiskZonesLayer";
import type { Incident } from "../shared/types";

type Props = { token: string; incidents: Incident[]; zonesVersion: number };

export default function DashboardMap({ token, incidents, zonesVersion }: Props) {
  const located = incidents.filter((i) => i.location !== null && i.status !== "CLOSED");
  return (
    <div>
      <MapView label="Map of risk zones and incidents" height={440}>
        {/* A new key re-loads the zones, e.g. after new risk predictions were computed. */}
        <RiskZonesLayer key={zonesVersion} token={token} />
        {located.map((incident) => (
          <CircleMarker
            // The key includes the status so the popup is rebuilt when the status changes.
            key={`${incident.id}-${incident.status}`}
            center={[incident.location!.lat, incident.location!.lon]}
            radius={incident.is_sos ? 11 : 8}
            pathOptions={{
              color: "#fff",
              weight: 2,
              fillColor: SEVERITY_COLOURS[incident.severity],
              fillOpacity: 0.95,
            }}
            eventHandlers={{
              add: (e) =>
                e.target.bindPopup(
                  popupContent([
                    `#${incident.id} ${incident.is_sos ? "SOS" : (incident.category?.name ?? "Uncategorised")}`,
                    `${SEVERITY_LABELS[incident.severity]} severity, ${STATUS_LABELS[incident.status].toLowerCase()}`,
                    incident.description,
                  ]),
                ),
            }}
          />
        ))}
      </MapView>
      <MapLegend
        extras={[
          { label: "Incident: critical", colour: SEVERITY_COLOURS.CRITICAL, round: true },
          { label: "Incident: high", colour: SEVERITY_COLOURS.HIGH, round: true },
          { label: "Incident: medium", colour: SEVERITY_COLOURS.MEDIUM, round: true },
          { label: "Incident: low", colour: SEVERITY_COLOURS.LOW, round: true },
        ]}
      />
    </div>
  );
}
