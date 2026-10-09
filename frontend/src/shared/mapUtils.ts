// Small helpers shared by the maps.

import type { RiskLevel } from "./types";

export const JAIPUR_CENTER: [number, number] = [26.9124, 75.8];

// Leaflet draws with plain colour values, so these mirror the theme (readable on both the
// light map and the dimmed dark map).
export const LEVEL_COLOURS: Record<RiskLevel, string> = {
  LOW: "#2e8b57",
  MODERATE: "#d4a017",
  HIGH: "#e0700f",
  CRITICAL: "#c0262d",
};

export const LEVEL_LABELS: Record<RiskLevel, string> = {
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const SEVERITY_COLOURS: Record<string, string> = {
  LOW: "#5b6b85",
  MEDIUM: "#2f6fe0",
  HIGH: "#e0700f",
  CRITICAL: "#c0262d",
};

export const YOU_COLOUR = "#2f6fe0";
export const POLICE_COLOUR = "#4a5bd6";
export const HOSPITAL_COLOUR = "#0b8f8a";

// Build popup content from plain text lines. Using textContent (not HTML strings) means a
// zone or incident name can never inject HTML or scripts into the page.
export function popupContent(lines: string[]): HTMLElement {
  const container = document.createElement("div");
  lines
    .filter((line) => line !== "")
    .forEach((line, index) => {
      const row = document.createElement("div");
      row.textContent = line;
      if (index === 0) row.style.fontWeight = "700";
      container.appendChild(row);
    });
  return container;
}

export function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(1)} km`;
}
