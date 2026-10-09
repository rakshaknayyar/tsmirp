// Dashboard analytics: plain incident counts from GET /analytics/summary (no estimates).
// Four headline numbers, then each breakdown as a labelled bar list: one colour for all bars
// (they show amounts, not categories), and the exact number written next to every bar, so the
// list doubles as a table.

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useId, useState } from "react";

import { apiGet } from "../shared/api";
import { LANGUAGE_NAMES, SEVERITY_LABELS, STATUS_LABELS } from "../shared/format";
import type { IncidentStatus } from "../shared/types";
import { Notice, Panel } from "../shared/ui";

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

type Row = { label: string; value: number };

function BarList({ title, rows, sort = true }: { title: string; rows: Row[]; sort?: boolean }) {
  const ordered = sort ? [...rows].sort((a, b) => b.value - a.value) : rows;
  const max = Math.max(1, ...ordered.map((r) => r.value));
  return (
    <Panel title={title}>
      {ordered.length === 0 ? (
        <p className="muted">No incidents in this period.</p>
      ) : (
        <ul className="bar-list">
          {ordered.map((row) => (
            <li className="bar-row" key={row.label}>
              <span className="bar-label" title={row.label}>
                {row.label}
              </span>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(row.value / max) * 100}%` }} />
              </span>
              <span className="bar-value">{row.value}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

const dayLabel = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short" });

function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function rows(counts: Record<string, number>, label: (key: string) => string = (k) => k): Row[] {
  return Object.entries(counts).map(([key, value]) => ({ label: label(key), value }));
}

export default function AnalyticsPanel({ token, refreshKey }: { token: string; refreshKey: number }) {
  const [days, setDays] = useState(7);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useId();

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
    <div className="stack-lg">
      <div className="toolbar">
        <div className="row">
          <label className="field-label" htmlFor={`${id}-days`}>
            Period
          </label>
          <select
            id={`${id}-days`}
            className="select select-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            {[1, 7, 30, 90].map((d) => (
              <option key={d} value={d}>
                {d === 1 ? "Today" : `Last ${d} days`}
              </option>
            ))}
          </select>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>
          <RefreshCw aria-hidden="true" />
          Refresh
        </button>
      </div>

      {error && (
        <Notice tone="danger" live="alert">
          {error}
        </Notice>
      )}

      {summary && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-value">{summary.total}</div>
              <div className="stat-label">Incidents reported</div>
            </div>
            <div className="stat">
              <div className="stat-value">{summary.sos}</div>
              <div className="stat-label">SOS alerts</div>
            </div>
            <div className="stat">
              <div className="stat-value">{summary.needs_review}</div>
              <div className="stat-label">Need a category check</div>
            </div>
            <div className="stat">
              <div className="stat-value">{summary.open_now}</div>
              <div className="stat-label">Open right now (any date)</div>
            </div>
          </div>

          <div className="breakdown-grid">
            <BarList
              title="By status"
              rows={rows(summary.by_status, (k) => STATUS_LABELS[k as IncidentStatus] ?? k)}
            />
            <BarList
              title="By severity"
              rows={rows(
                summary.by_severity,
                (k) => SEVERITY_LABELS[k as keyof typeof SEVERITY_LABELS] ?? k,
              )}
            />
            <BarList
              title="By category"
              rows={rows(summary.by_category, (k) =>
                k === "uncategorised" ? "No category (incl. SOS)" : sentenceCase(k.replace(/_/g, " ")),
              )}
            />
            <BarList
              title="By language"
              rows={rows(summary.by_language, (k) => LANGUAGE_NAMES[k] ?? k)}
            />
          </div>

          <BarList
            title="Per day (India time)"
            sort={false}
            rows={summary.per_day.map((d) => ({
              label: dayLabel.format(new Date(`${d.date}T00:00:00`)),
              value: d.count,
            }))}
          />
          <p className="small muted">{summary.note}</p>
        </>
      )}
    </div>
  );
}
