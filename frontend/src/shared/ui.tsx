// Small, reusable building blocks, so every screen looks and behaves the same way.
// Styles are in src/styles/app.css.

import { AlertTriangle, CheckCircle2, Info, OctagonAlert } from "lucide-react";
import type { ReactNode } from "react";

type Tone = "info" | "success" | "warning" | "danger";

export function Panel({
  title,
  description,
  actions,
  children,
  id,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section className="panel" aria-labelledby={headingId} id={id}>
      <div className="panel-header">
        <div>
          <h2 className="panel-title" id={headingId}>
            {title}
          </h2>
          {description && <p className="panel-description">{description}</p>}
        </div>
        {actions && <div className="row">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

const NOTICE_ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: OctagonAlert,
};

// role="alert" for things that need attention now; "status" for quiet confirmations.
export function Notice({
  tone = "info",
  title,
  children,
  live,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  live?: "alert" | "status";
}) {
  const Icon = NOTICE_ICONS[tone];
  return (
    <div className={`notice notice-${tone}`} role={live}>
      <Icon aria-hidden="true" />
      <div>
        {title && <strong className="notice-title">{title}</strong>}
        {children}
      </div>
    </div>
  );
}

export function Badge({
  tone,
  children,
}: {
  tone?: Tone | "accent";
  children: ReactNode;
}) {
  return <span className={tone ? `badge badge-${tone}` : "badge"}>{children}</span>;
}

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {children}
      {hint && (
        <span className="field-hint" id={`${id}-hint`}>
          {hint}
        </span>
      )}
    </div>
  );
}

// An on/off switch that screen readers announce as a switch.
export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <div className="switch-row">
      <div>
        <strong>{label}</strong>
        {description && <p className="muted small">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        className="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon}
      <strong>{title}</strong>
      {children && <span>{children}</span>}
    </div>
  );
}

export function LiveIndicator({ connected }: { connected: boolean }) {
  return (
    <span className="live" data-on={connected}>
      {connected ? "Live updates on" : "Reconnecting"}
    </span>
  );
}
