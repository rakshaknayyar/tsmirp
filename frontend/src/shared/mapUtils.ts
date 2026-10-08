// Small helpers shared by the maps.

import type { RiskLevel } from "./types";

export const JAIPUR_CENTER: [number, number] = [26.9124, 75.8];

export const LEVEL_COLOURS: Record<RiskLevel, string> = {
  LOW: "#2e7d32",
  MODERATE: "#f9a825",
  HIGH: "#ef6c00",
  CRITICAL: "#c62828",
};

export const SEVERITY_COLOURS: Record<string, string> = {
  LOW: "#2e7d32",
  MEDIUM: "#1565c0",
  HIGH: "#ef6c00",
  CRITICAL: "#c62828",
};

// Build popup content from plain text lines. Using textContent (not HTML strings) means a
// zone or incident name can never inject HTML or scripts into the page.
export function popupContent(lines: string[]): HTMLElement {
  const container = document.createElement("div");
  lines.forEach((line, index) => {
    const row = document.createElement("div");
    row.textContent = line;
    if (index === 0) row.style.fontWeight = "bold";
    container.appendChild(row);
  });
  return container;
}

export function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(1)} km`;
}
