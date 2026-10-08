// Dashboard map: risk zones and every incident whose location the operator may see
// (consent or SOS rules are applied by the API; incidents without a location are not drawn).

import { CircleMarker } from "react-leaflet";

import MapView from "../shared/MapView";
import { popupContent, SEVERITY_COLOURS } from "../shared/mapUtils";
import RiskZonesLayer from "../shared/RiskZonesLayer";
import type { Incident } from "../shared/types";

export default function DashboardMap({ token, incidents }: { token: string; incidents: Incident[] }) {
  const located = incidents.filter((i) => i.location !== null && i.status !== "CLOSED");
  return (
    <MapView height={380}>
      <RiskZonesLayer token={token} />
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
            fillOpacity: 0.9,
          }}
          eventHandlers={{
            add: (e) =>
              e.target.bindPopup(
                popupContent([
                  `#${incident.id} ${incident.category?.name ?? "Uncategorised"}`,
                  `Severity ${incident.severity} - ${incident.status}`,
                  incident.description,
                ]),
              ),
          }}
        />
      ))}
    </MapView>
  );
}
