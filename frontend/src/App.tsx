// Top-level page. A tiny "router" based on the part of the URL after #:
//   #/tourist   -> tourist app
//   #/dashboard -> authority dashboard
//   anything else -> home page with links and system health

import { useEffect, useState } from "react";

import DashboardApp from "./dashboard/DashboardApp";
import { apiGet } from "./shared/api";
import SimulationNotice from "./shared/SimulationNotice";
import TouristApp from "./tourist/TouristApp";

type Health = {
  status: string;
  api: string;
  database: { status: string; postgis_version?: string | null; error?: string };
  redis: { status: string; error?: string };
};

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

export default function App() {
  const route = useHashRoute();

  let page;
  if (route === "#/tourist") page = <TouristApp />;
  else if (route === "#/dashboard") page = <DashboardApp />;
  else page = <Home />;

  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        maxWidth: 1100,
        margin: "1.5rem auto",
        padding: "0 16px",
      }}
    >
      <h1>
        <a href="#/" style={{ color: "inherit", textDecoration: "none" }}>
          TSMIRP
        </a>
      </h1>
      {page}
    </main>
  );
}

function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Health>("/health")
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <>
      <p>Tourist Safety Monitoring and Incident Response Platform (SIH25002 prototype).</p>
      <SimulationNotice />

      <h2>Apps</h2>
      <ul>
        <li>
          <a href="#/tourist">Tourist app</a>
        </li>
        <li>
          <a href="#/dashboard">Authority dashboard</a>
        </li>
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
    </>
  );
}
