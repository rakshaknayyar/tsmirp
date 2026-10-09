// Incident list for operators: filter, change status, override the automatic category or
// severity (every override is audited by the API) and open the resource picker.

import { Inbox } from "lucide-react";
import { Fragment, useState } from "react";

import { apiRequest } from "../shared/api";
import {
  formatDateTime,
  LANGUAGE_NAMES,
  SEVERITY_LABELS,
  STATUS_LABELS,
  statusTone,
} from "../shared/format";
import { SEVERITIES } from "../shared/types";
import type { Category, Incident, IncidentStatus } from "../shared/types";
import { Badge, EmptyState, Notice, Panel } from "../shared/ui";
import ResourcePicker from "./ResourcePicker";

// Buttons offered for each status. Mirrors the backend lifecycle, except ASSIGNED, which is
// set by assigning a resource (the "Recommend units" button).
const NEXT_STATUSES: Record<IncidentStatus, IncidentStatus[]> = {
  NEW: ["ACKNOWLEDGED"],
  ACKNOWLEDGED: ["RESOLVED"],
  ASSIGNED: ["EN_ROUTE", "RESOLVED"],
  EN_ROUTE: ["RESOLVED"],
  RESOLVED: ["CLOSED", "ACKNOWLEDGED"],
  CLOSED: [],
};

const ACTION_LABELS: Record<IncidentStatus, string> = {
  NEW: "New",
  ACKNOWLEDGED: "Acknowledge",
  ASSIGNED: "Assign",
  EN_ROUTE: "Mark on the way",
  RESOLVED: "Resolve",
  CLOSED: "Close",
};

const FILTERS = [
  { id: "open", label: "Open", test: (i: Incident) => i.status !== "RESOLVED" && i.status !== "CLOSED" },
  { id: "review", label: "Needs review", test: (i: Incident) => i.needs_review },
  { id: "sos", label: "SOS", test: (i: Incident) => i.is_sos },
  { id: "all", label: "All", test: () => true },
] as const;

type Props = {
  token: string;
  incidents: Incident[];
  categories: Category[];
  onIncidentChanged: (incident: Incident) => void;
};

export default function IncidentsTable({ token, incidents, categories, onIncidentChanged }: Props) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("open");
  const [pickerFor, setPickerFor] = useState<number | null>(null); // incident id
  const [error, setError] = useState<string | null>(null);

  const shown = incidents.filter(FILTERS.find((f) => f.id === filter)!.test);

  async function changeStatus(incident: Incident, status: IncidentStatus) {
    setError(null);
    try {
      const updated = await apiRequest<Incident>("PATCH", `/incidents/${incident.id}/status`, {
        token,
        body: { status },
      });
      onIncidentChanged(updated);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  // Operator override of category and/or severity (PATCH /incidents/{id}).
  async function override(incident: Incident, change: { category_code?: string; severity?: string }) {
    setError(null);
    try {
      const updated = await apiRequest<Incident>("PATCH", `/incidents/${incident.id}`, {
        token,
        body: change,
      });
      onIncidentChanged(updated);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Panel
      title="Incidents"
      description="Change the category or severity from the drop-downs; every change is recorded in the audit log."
      actions={
        <div className="segmented" role="group" aria-label="Show incidents">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label} ({incidents.filter(f.test).length})
            </button>
          ))}
        </div>
      }
    >
      <div className="stack">
        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}
        {shown.length === 0 ? (
          <EmptyState icon={<Inbox aria-hidden="true" />} title="Nothing here">
            No incidents match this filter.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Incident</th>
                  <th scope="col">Category</th>
                  <th scope="col">Severity</th>
                  <th scope="col">Status</th>
                  <th scope="col">Description</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((incident) => (
                  <Fragment key={incident.id}>
                    <tr className={incident.is_sos ? "row-sos" : undefined}>
                      <td className="nowrap">
                        <strong>#{incident.id}</strong> {incident.is_sos && <Badge tone="danger">SOS</Badge>}
                        <div className="small muted">{formatDateTime(incident.created_at)}</div>
                      </td>
                      <td>
                        <select
                          className="select select-sm"
                          aria-label={`Category of incident ${incident.id}`}
                          value={incident.category?.code ?? ""}
                          onChange={(e) => void override(incident, { category_code: e.target.value })}
                        >
                          {!incident.category && <option value="">Uncategorised</option>}
                          {categories.map((c) => (
                            <option key={c.code} value={c.code}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                        <div className="small muted">
                          {incident.category?.department ?? "No department yet"}
                          {incident.confidence !== null &&
                            `, auto ${Math.round(incident.confidence * 100)}%`}
                        </div>
                        {incident.needs_review && <Badge tone="warning">Needs review</Badge>}
                      </td>
                      <td>
                        <select
                          className="select select-sm"
                          aria-label={`Severity of incident ${incident.id}`}
                          value={incident.severity}
                          onChange={(e) => void override(incident, { severity: e.target.value })}
                        >
                          {SEVERITIES.map((s) => (
                            <option key={s} value={s}>
                              {SEVERITY_LABELS[s]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <Badge tone={statusTone(incident.status)}>{STATUS_LABELS[incident.status]}</Badge>
                      </td>
                      <td className="cell-description">
                        {incident.description}
                        {incident.language !== "en" && (
                          <div className="small muted">
                            {LANGUAGE_NAMES[incident.language] ?? incident.language}, translated for
                            classification
                          </div>
                        )}
                      </td>
                      <td>
                        <div className="row">
                          {NEXT_STATUSES[incident.status].map((next) => (
                            <button
                              key={next}
                              className={next === "ACKNOWLEDGED" && incident.status === "NEW" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
                              onClick={() => void changeStatus(incident, next)}
                            >
                              {incident.status === "RESOLVED" && next === "ACKNOWLEDGED" ? "Reopen" : ACTION_LABELS[next]}
                            </button>
                          ))}
                          {incident.status === "ACKNOWLEDGED" && incident.location && (
                            <button className="btn btn-primary btn-sm" onClick={() => setPickerFor(incident.id)}>
                              Recommend units
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {pickerFor === incident.id && (
                      <tr className="detail-row">
                        <td colSpan={6}>
                          <ResourcePicker
                            incident={incident}
                            token={token}
                            onAssigned={(updated) => {
                              onIncidentChanged(updated);
                              setPickerFor(null);
                            }}
                            onClose={() => setPickerFor(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}
