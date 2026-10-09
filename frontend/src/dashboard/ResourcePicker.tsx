// Shows the recommended units for one incident and lets an operator assign one.
// Assignment is SIMULATED: it is recorded in the database, no real unit is contacted.

import { Hospital, Flame, ShieldHalf, X } from "lucide-react";
import { useEffect, useState } from "react";

import { apiGet, apiRequest } from "../shared/api";
import { formatDistance } from "../shared/mapUtils";
import type { Incident, RecommendedResource } from "../shared/types";
import { Badge, Notice } from "../shared/ui";

type Props = {
  incident: Incident;
  token: string;
  onAssigned: (incident: Incident) => void;
  onClose: () => void;
};

const TYPE_LABELS = { police_station: "Police station", hospital: "Hospital", fire_station: "Fire station" };
const TYPE_ICONS = { police_station: ShieldHalf, hospital: Hospital, fire_station: Flame };
const AVAILABILITY_TONES = { AVAILABLE: "success", BUSY: "warning", OFFLINE: undefined } as const;

export default function ResourcePicker({ incident, token, onAssigned, onClose }: Props) {
  const [resources, setResources] = useState<RecommendedResource[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<RecommendedResource[]>(`/incidents/${incident.id}/recommended-resources?k=5`, token)
      .then(setResources)
      .catch((err: Error) => setError(err.message));
  }, [incident.id, token]);

  async function assign(resource: RecommendedResource) {
    setError(null);
    try {
      const result = await apiRequest<{ incident: Incident }>(
        "POST",
        `/incidents/${incident.id}/assign`,
        { token, body: { resource_id: resource.id } },
      );
      onAssigned(result.incident);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <div>
          <h3>Recommended units for incident #{incident.id}</h3>
          <p className="small muted">
            Available first, then matching capability, then nearer. Distances are straight-line;
            availability is simulated.
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          <X aria-hidden="true" />
          Close
        </button>
      </div>
      {error && (
        <Notice tone="danger" live="alert">
          {error}
        </Notice>
      )}
      {resources === null && !error && <p className="muted">Finding the nearest units…</p>}
      {resources?.length === 0 && <p className="muted">No suitable units within 25 km.</p>}
      {resources && resources.length > 0 && (
        <ul className="list">
          {resources.map((r) => {
            const Icon = TYPE_ICONS[r.resource_type];
            return (
              <li className="list-item" key={r.id}>
                <span className="list-item-icon">
                  <Icon aria-hidden="true" />
                </span>
                <span className="list-item-main">
                  <span className="list-item-title">{r.name}</span>
                  <span className="list-item-sub">
                    {TYPE_LABELS[r.resource_type]}, {formatDistance(r.distance_m)} straight-line
                    {r.capability_match && ", has an emergency department"}
                  </span>
                </span>
                <Badge tone={AVAILABILITY_TONES[r.availability_sim]}>
                  {r.availability_sim.toLowerCase()} (simulated)
                </Badge>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={r.availability_sim !== "AVAILABLE"}
                  onClick={() => void assign(r)}
                >
                  Assign (simulated)
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
