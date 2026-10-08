import { useEffect, useState } from "react";

import { apiGet } from "./shared/api";

type Health = {
  status: string;
  api: string;
  database: { status: string; postgis_version?: string | null; error?: string };
  redis: { status: string; error?: string };
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Health>("/health")
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "2rem auto", padding: "0 16px" }}>
      <h1>TSMIRP</h1>
      <p>
        Tourist Safety Monitoring and Incident Response Platform (SIH25002 prototype).
        Decision support only, not a replacement for police or emergency services.
      </p>
      <p>
        <strong>Prototype:</strong> dispatch, SMS and e-mail are simulated. In a real emergency
        call 112.
      </p>

      <h2>Apps</h2>
      <ul>
        <li>Tourist app (built in later phases)</li>
        <li>Authority dashboard (built in later phases)</li>
      </ul>

      <h2>System health</h2>
      {error && <p>Could not reach the API: {error}</p>}
      {!error && !health && <p>Checking...</p>}
      {health && (
        <ul>
          <li>Overall: {health.status}</li>
          <li>API: {health.api}</li>
          <li>
            Database: {health.database.status}
            {health.database.postgis_version && ` (PostGIS ${health.database.postgis_version})`}
          </li>
          <li>Redis: {health.redis.status}</li>
        </ul>
      )}
    </main>
  );
}
