// Shows the recommended resources for one incident and lets an operator assign one.
// Assignment is SIMULATED: it is recorded in the database, no real unit is contacted.

import { useEffect, useState } from "react";

import { apiGet, apiRequest } from "../shared/api";
import type { Incident, RecommendedResource } from "../shared/types";

type Props = {
  incident: Incident;
  token: string;
  onAssigned: (incident: Incident) => void;
  onClose: () => void;
};

function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(1)} km`;
}

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
    <div style={{ border: "1px solid #999", borderRadius: 6, padding: 8, margin: "6px 0" }}>
      <strong>Recommended resources for incident #{incident.id}</strong>{" "}
      <button onClick={onClose}>Close</button>
      <p style={{ fontSize: 13, margin: "4px 0" }}>
        Ranked: available first, then matching capability, then nearer. Distances are
        straight-line approximations; availability is simulated.
      </p>
      {error && <p role="alert">{error}</p>}
      {resources === null && !error && <p>Loading...</p>}
      {resources?.length === 0 && <p>No suitable resources found.</p>}
      <ol>
        {resources?.map((r) => (
          <li key={r.id}>
            {r.name} ({r.resource_type.replace("_", " ")}) - {formatDistance(r.distance_m)}{" "}
            straight-line - {r.availability_sim}
            {r.capability_match && " - has emergency department"}{" "}
            <button disabled={r.availability_sim !== "AVAILABLE"} onClick={() => assign(r)}>
              Assign (simulated)
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
