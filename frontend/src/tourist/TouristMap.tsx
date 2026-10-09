// Tourist map: risk zones, "you are here", and the nearest police stations and hospitals,
// with the same places listed underneath (easier to read on a phone than map pins).

import { Hospital, MapPinOff, ShieldHalf } from "lucide-react";
import { useEffect, useState } from "react";
import { Circle, CircleMarker, Popup, useMap } from "react-leaflet";

import { apiGet } from "../shared/api";
import MapLegend from "../shared/MapLegend";
import MapView from "../shared/MapView";
import {
  formatDistance,
  HOSPITAL_COLOUR,
  POLICE_COLOUR,
  popupContent,
  YOU_COLOUR,
} from "../shared/mapUtils";
import RiskZonesLayer from "../shared/RiskZonesLayer";
import type { NearbyResource, Position } from "../shared/types";
import { EmptyState, Panel } from "../shared/ui";

// Moves the map to the tourist's position whenever it changes.
function FollowPosition({ position }: { position: Position }) {
  const map = useMap();
  useEffect(() => {
    map.setView([position.lat, position.lon], Math.max(map.getZoom(), 15));
  }, [map, position.lat, position.lon]);
  return null;
}

export default function TouristMap({ token, position }: { token: string; position: Position | null }) {
  const [help, setHelp] = useState<NearbyResource[]>([]);

  useEffect(() => {
    if (!position) {
      setHelp([]);
      return;
    }
    const where = `lat=${position.lat}&lon=${position.lon}&k=3`;
    Promise.all([
      apiGet<NearbyResource[]>(`/nearby-resources?${where}&type=police_station`, token),
      apiGet<NearbyResource[]>(`/nearby-resources?${where}&type=hospital`, token),
    ])
      .then(([police, hospitals]) => setHelp([...police, ...hospitals]))
      .catch(() => setHelp([]));
  }, [token, position]);

  return (
    <Panel
      title="Map and help nearby"
      description="Coloured areas show relative risk levels. Distances are straight-line, so the walk or drive will be longer."
    >
      <MapView label="Map of risk zones and nearby help" height={400}>
        <RiskZonesLayer token={token} />
        {position && (
          <>
            <FollowPosition position={position} />
            <Circle
              center={[position.lat, position.lon]}
              radius={position.accuracy_m}
              pathOptions={{ color: YOU_COLOUR, weight: 1, fillOpacity: 0.12 }}
            />
            <CircleMarker
              center={[position.lat, position.lon]}
              radius={9}
              pathOptions={{ color: "#fff", fillColor: YOU_COLOUR, fillOpacity: 1, weight: 3 }}
            >
              <Popup>{position.simulated ? "You (demo position)" : "You are here"}</Popup>
            </CircleMarker>
          </>
        )}
        {help.map((r) => (
          <CircleMarker
            key={r.id}
            center={[r.lat, r.lon]}
            radius={7}
            pathOptions={{
              color: "#fff",
              weight: 2,
              fillOpacity: 1,
              fillColor: r.resource_type === "hospital" ? HOSPITAL_COLOUR : POLICE_COLOUR,
            }}
            eventHandlers={{
              add: (e) =>
                e.target.bindPopup(
                  popupContent([
                    r.name,
                    r.resource_type === "hospital" ? "Hospital" : "Police station",
                    `${formatDistance(r.distance_m)} straight-line`,
                  ]),
                ),
            }}
          />
        ))}
      </MapView>
      <MapLegend
        extras={[
          { label: "You", colour: YOU_COLOUR, round: true },
          { label: "Police", colour: POLICE_COLOUR, round: true },
          { label: "Hospital", colour: HOSPITAL_COLOUR, round: true },
        ]}
      />

      <div className="mt-md">
        {help.length === 0 ? (
          <EmptyState icon={<MapPinOff aria-hidden="true" />} title="No position shared yet">
            Share your location above to see the nearest police stations and hospitals.
          </EmptyState>
        ) : (
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
                    {r.resource_type === "hospital" ? "Hospital" : "Police station"}
                  </span>
                </span>
                <span className="nowrap">{formatDistance(r.distance_m)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="small muted mt-sm">
          Places from OpenStreetMap contributors (ODbL).
        </p>
      </div>
    </Panel>
  );
}
