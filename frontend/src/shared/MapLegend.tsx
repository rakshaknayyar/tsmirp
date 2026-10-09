// Key for the map colours. Risk levels are relative estimates, which the legend says.

import { LEVEL_COLOURS, LEVEL_LABELS } from "./mapUtils";
import type { RiskLevel } from "./types";

type Extra = { label: string; colour: string; round?: boolean };

export default function MapLegend({ extras = [] }: { extras?: Extra[] }) {
  const levels = Object.keys(LEVEL_COLOURS) as RiskLevel[];
  return (
    <div className="legend" aria-label="Map key">
      {levels.map((level) => (
        <span className="legend-item" key={level}>
          <span
            className="legend-swatch"
            style={{ background: LEVEL_COLOURS[level] }}
            aria-hidden="true"
          />
          {LEVEL_LABELS[level]} risk
        </span>
      ))}
      {extras.map((extra) => (
        <span className="legend-item" key={extra.label}>
          <span
            className="legend-swatch"
            style={{ background: extra.colour, borderRadius: extra.round ? "50%" : undefined }}
            aria-hidden="true"
          />
          {extra.label}
        </span>
      ))}
      <span>Levels are relative estimates, not predictions of crime.</span>
    </div>
  );
}
