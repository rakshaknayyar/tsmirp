// Dashboard analytics: plain incident counts from GET /analytics/summary (no estimates),
// shown as small tables so every number can be checked against the incident list.

import { useCallback, useEffect, useState } from "react";

import { apiGet } from "../shared/api";

type Summary = {
  days: number;
  total: number;
  sos: number;
  open_now: number;
  needs_review: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  by_language: Record<string, number>;
  per_day: { date: string; count: number }[];
  note: string;
};

type CountTableProps = {
  title: string;
  counts: Record<string, number>;
  byCount?: boolean; // largest first (default); false keeps the given order, e.g. dates
};

function CountTable({ title, counts, byCount = true }: CountTableProps) {
  const rows = Object.entries(counts);
  if (byCount) rows.sort((a, b) => b[1] - a[1]);
  return (
    <table style={{ borderCollapse: "collapse", minWidth: 140 }}>
      <thead>
        <tr>
          <th colSpan={2} style={{ textAlign: "left" }}>
            {title}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={2}>none</td>
          </tr>
        ) : (
          rows.map(([key, n]) => (
            <tr key={key}>
              <td style={{ paddingRight: 8 }}>{key}</td>
              <td style={{ textAlign: "right" }}>{n}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

export default function AnalyticsPanel({ token, refreshKey }: { token: string; refreshKey: number }) {
  const [days, setDays] = useState(7);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGet<Summary>(`/analytics/summary?days=${days}`, token)
      .then((result) => {
        setSummary(result);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [days, token]);

  useEffect(() => load(), [load, refreshKey]);

  return (
    <section>
      <h2>Analytics</h2>
      <p>
        Last{" "}
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[1, 7, 30, 90].map((d) => (
            <option key={d} value={d}>
              {d} day{d > 1 ? "s" : ""}
            </option>
          ))}
        </select>{" "}
        <button onClick={load}>Refresh</button>
      </p>
      {error && <p role="alert">{error}</p>}
      {summary && (
        <>
          <p>
            <strong>{summary.total}</strong> incidents ({summary.sos} SOS),{" "}
            <strong>{summary.needs_review}</strong> need a category check,{" "}
            <strong>{summary.open_now}</strong> open right now (any date).
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
            <CountTable title="Status" counts={summary.by_status} />
            <CountTable title="Severity" counts={summary.by_severity} />
            <CountTable title="Category" counts={summary.by_category} />
            <CountTable title="Language" counts={summary.by_language} />
            <CountTable
              title="Per day (India time)"
              counts={Object.fromEntries(summary.per_day.map((d) => [d.date, d.count]))}
              byCount={false}
            />
          </div>
          <p style={{ fontSize: 12 }}>{summary.note}</p>
        </>
      )}
    </section>
  );
}
