// Turning API values into words and times people can read.

import type { Incident, IncidentStatus } from "./types";

export const STATUS_LABELS: Record<IncidentStatus, string> = {
  NEW: "New",
  ACKNOWLEDGED: "Acknowledged",
  ASSIGNED: "Unit assigned",
  EN_ROUTE: "On the way",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
};

export const SEVERITY_LABELS: Record<Incident["severity"], string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const SEVERITY_TONES = {
  LOW: undefined,
  MEDIUM: "info",
  HIGH: "warning",
  CRITICAL: "danger",
} as const;

export function statusTone(status: IncidentStatus) {
  if (status === "RESOLVED" || status === "CLOSED") return "success" as const;
  if (status === "NEW") return "warning" as const;
  return "info" as const;
}

const dateTime = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const dateOnly = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function formatDate(iso: string): string {
  return dateOnly.format(new Date(iso));
}

export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] || fullName;
}

export const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  hi: "Hindi",
  "hi-Latn": "Romanised Hindi",
};
