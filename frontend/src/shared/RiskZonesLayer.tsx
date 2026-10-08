// Draws the risk zones that are inside the visible part of the map.
// It asks the API again (GET /risk-zone?bbox=...) every time the map is moved or zoomed.
// Hand-drawn "area" zones always show; model "grid" cells only show when the model's level
// for the current 6-hour period is MODERATE or above (LOW cells would cover the whole map).

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
  kind: "area" | "grid";
  level: RiskLevel; // the level right now
  level_source: string; // where the level comes from (fixed, or which model and period)
  score: number | null;
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
      .then((all) =>
        setZones({
          ...all,
          features: all.features.filter(
            (f) => f.properties.kind === "area" || f.properties.level !== "LOW",
          ),
        }),
      )
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
      style={(feature) => {
        const p = feature?.properties as ZoneProperties | undefined;
        const colour = p ? LEVEL_COLOURS[p.level] : "#666";
        return p?.kind === "grid"
          ? { color: colour, weight: 0.5, fillOpacity: 0.35, dashArray: "2 2" }
          : { color: colour, weight: 2, fillOpacity: 0.2 };
      }}
      onEachFeature={(feature, layer) => {
        const p = feature.properties as ZoneProperties;
        layer.bindPopup(
          popupContent([
            p.name,
            `Relative risk level: ${p.level}` +
              (p.score !== null ? ` (score ${p.score.toFixed(2)})` : ""),
            `Source: ${p.level_source}`,
            "Decision support only - not a prediction that a crime will occur.",
            p.is_synthetic ? "Based on synthetic demonstration data" : "",
            p.description ?? "",
          ]),
        );
      }}
    />
  );
}
