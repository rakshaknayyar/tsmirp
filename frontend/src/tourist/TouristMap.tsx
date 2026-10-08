// Tourist map: risk zones, "you are here", and the nearest police stations and hospitals.

import { useEffect, useState } from "react";
import { Circle, CircleMarker, Popup, useMap } from "react-leaflet";

import { apiGet } from "../shared/api";
import MapView from "../shared/MapView";
import { formatDistance, popupContent } from "../shared/mapUtils";
import RiskZonesLayer from "../shared/RiskZonesLayer";
import type { NearbyResource, Position } from "../shared/types";

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
    if (!position) return;
    const where = `lat=${position.lat}&lon=${position.lon}&k=3`;
    Promise.all([
      apiGet<NearbyResource[]>(`/nearby-resources?${where}&type=police_station`, token),
      apiGet<NearbyResource[]>(`/nearby-resources?${where}&type=hospital`, token),
    ])
      .then(([police, hospitals]) => setHelp([...police, ...hospitals]))
      .catch(() => setHelp([]));
  }, [token, position]);

  return (
    <>
      <MapView>
        <RiskZonesLayer token={token} />
        {position && (
          <>
            <FollowPosition position={position} />
            <Circle
              center={[position.lat, position.lon]}
              radius={position.accuracy_m}
              pathOptions={{ color: "#1565c0", weight: 1, fillOpacity: 0.1 }}
            />
            <CircleMarker
              center={[position.lat, position.lon]}
              radius={8}
              pathOptions={{ color: "#fff", fillColor: "#1565c0", fillOpacity: 1, weight: 2 }}
            >
              <Popup>{position.simulated ? "You (demo position)" : "You are here"}</Popup>
            </CircleMarker>
          </>
        )}
        {help.map((r) => (
          <CircleMarker
            key={r.id}
            center={[r.lat, r.lon]}
            radius={6}
            pathOptions={{ color: r.resource_type === "hospital" ? "#c62828" : "#283593" }}
            eventHandlers={{
              add: (e) =>
                e.target.bindPopup(
                  popupContent([
                    r.name,
                    r.resource_type.replace("_", " "),
                    `${formatDistance(r.distance_m)} straight-line`,
                  ]),
                ),
            }}
          />
        ))}
      </MapView>
      {help.length > 0 && (
        <>
          <h3>Nearest help (straight-line distance; the route will be longer)</h3>
          <ul>
            {help.map((r) => (
              <li key={r.id}>
                {r.resource_type === "hospital" ? "Hospital" : "Police"}: {r.name} -{" "}
                {formatDistance(r.distance_m)}
              </li>
            ))}
          </ul>
          <p style={{ fontSize: 12 }}>Locations from OpenStreetMap contributors (ODbL).</p>
        </>
      )}
    </>
  );
}
