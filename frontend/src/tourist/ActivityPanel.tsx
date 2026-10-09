// The tourist's own reports (with live status) and the notifications sent to them.
// Simulated SMS / e-mail notifications are labelled as such.

import { Bell, FileText, Inbox, RefreshCw, Siren } from "lucide-react";

import {
  formatDateTime,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  STATUS_LABELS,
  statusTone,
} from "../shared/format";
import type { AppNotification, Incident } from "../shared/types";
import { Badge, EmptyState, Panel } from "../shared/ui";

const CHANNEL_LABELS: Record<AppNotification["channel"], string | null> = {
  in_app: null,
  sms_sandbox: "Simulated SMS",
  email_sandbox: "Simulated e-mail",
};

type Props = {
  incidents: Incident[];
  notifications: AppNotification[];
  onRefresh: () => void;
};

export default function ActivityPanel({ incidents, notifications, onRefresh }: Props) {
  const refresh = (
    <button className="btn btn-secondary btn-sm" onClick={onRefresh}>
      <RefreshCw aria-hidden="true" />
      Refresh
    </button>
  );

  return (
    <>
      <Panel title="My reports" description="Status changes appear here as the control room works on them." actions={refresh}>
        {incidents.length === 0 ? (
          <EmptyState icon={<Inbox aria-hidden="true" />} title="No reports yet">
            Reports you send and SOS alerts will show up here.
          </EmptyState>
        ) : (
          <ul className="list">
            {incidents.map((incident) => (
              <li className="list-item list-item-top" key={incident.id}>
                <span className="list-item-icon">
                  {incident.is_sos ? <Siren aria-hidden="true" /> : <FileText aria-hidden="true" />}
                </span>
                <span className="list-item-main">
                  <span className="list-item-title">
                    {incident.is_sos ? "SOS" : (incident.category?.name ?? "Waiting for a category")}{" "}
                    <span className="muted small">#{incident.id}</span>
                  </span>
                  <span className="list-item-sub">{incident.description}</span>
                  <span className="row mt-xs">
                    <Badge tone={statusTone(incident.status)}>{STATUS_LABELS[incident.status]}</Badge>
                    <Badge tone={SEVERITY_TONES[incident.severity]}>
                      {SEVERITY_LABELS[incident.severity]} severity
                    </Badge>
                    <span className="small muted">{formatDateTime(incident.created_at)}</span>
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Notifications" description="Alerts and updates sent to you, newest first.">
        {notifications.length === 0 ? (
          <EmptyState icon={<Bell aria-hidden="true" />} title="No notifications">
            Geofence alerts and updates about your reports will appear here.
          </EmptyState>
        ) : (
          <ul className="list">
            {notifications.map((n) => (
              <li className="list-item list-item-top" key={n.id}>
                <span className="list-item-main">
                  <span className="list-item-title">
                    {n.title}{" "}
                    {CHANNEL_LABELS[n.channel] && <Badge tone="warning">{CHANNEL_LABELS[n.channel]}</Badge>}
                  </span>
                  <span className="list-item-sub">{n.body}</span>
                  <span className="small muted">{formatDateTime(n.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}
