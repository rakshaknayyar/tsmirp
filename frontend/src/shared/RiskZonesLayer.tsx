// Draws the risk zones that are inside the visible part of the map.
// It asks the API again (GET /risk-zone?bbox=...) every time the map is moved or zoomed.

import type { FeatureCollection, Polygon } from "geojson";
import { useCallback, useEffect, useState } from "react";
import { GeoJSON, useMap, useMapEvents } from "react-leaflet";

import { apiGet } from "./api";
import { LEVEL_COLOURS, popupContent } from "./mapUtils";
import type { RiskLevel } from "./types";

type ZoneProperties = {
  id: number;
  name: string;
  description: string | null;
  level: RiskLevel;
  is_synthetic: boolean;
};
type ZoneCollection = FeatureCollection<Polygon, ZoneProperties>;

export default function RiskZonesLayer({ token }: { token: string }) {
  const map = useMap();
  const [zones, setZones] = useState<ZoneCollection | null>(null);

  const load = useCallback(() => {
    const b = map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
      .map((n) => n.toFixed(5))
      .join(",");
    apiGet<ZoneCollection>(`/risk-zone?bbox=${bbox}`, token)
      .then(setZones)
      .catch(() => setZones(null)); // e.g. zoomed out too far: just show no zones
  }, [map, token]);

  useEffect(() => load(), [load]);
  useMapEvents({ moveend: load });

  if (zones === null) return null;
  return (
    <GeoJSON
      // GeoJSON layers do not redraw when their data changes, so a new key forces it.
      key={zones.features.map((f) => f.properties.id).join("-")}
      data={zones}
      style={(feature) => ({
        color: feature ? LEVEL_COLOURS[(feature.properties as ZoneProperties).level] : "#666",
        weight: 2,
        fillOpacity: 0.2,
      })}
      onEachFeature={(feature, layer) => {
        const p = feature.properties as ZoneProperties;
        layer.bindPopup(
          popupContent([
            p.name,
            `Relative risk level: ${p.level} (decision support, not a prediction)`,
            p.is_synthetic ? "Synthetic demonstration data" : "",
            p.description ?? "",
          ]),
        );
      }}
    />
  );
}
