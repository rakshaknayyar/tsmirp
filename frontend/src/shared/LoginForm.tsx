// The one log-in screen for the whole site. A sliding switch at the top chooses who is logging
// in: a tourist (goes to the tourist app) or authority staff (goes to the control room).
// Tourists can also create an account here; staff accounts are created by an administrator.
// An account of the wrong kind (e.g. a tourist with "Authority" selected) is refused with a
// clear message. A "Back to home" arrow above the card returns to the home page.

import {
  Activity,
  ArrowLeft,
  Building2,
  Compass,
  Eye,
  EyeOff,
  FileClock,
  Languages,
  MapPinned,
  ShieldCheck,
  Siren,
} from "lucide-react";
import { useId, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest, login } from "./api";
import { link } from "./router";
import { setSession } from "./session";
import type { SessionKind } from "./session";
import { Notice } from "./ui";
import { STAFF_ROLES } from "./types";

const COPY = {
  tourist: {
    title: "Travel Jaipur with help close by",
    lead: "Your personal safety companion for the trip: alerts near higher-risk areas, an SOS button and a digital tourist ID.",
    points: [
      {
        icon: Siren,
        text: "Press SOS to alert the control room (simulated in this prototype)",
      },
      { icon: MapPinned, text: "Share your location only when you choose to" },
      { icon: Languages, text: "Report a problem in English or Hindi" },
    ],
    formTitle: "Log in to your tourist account",
  },
  staff: {
    title: "Control room",
    lead: "For police, tourism and emergency staff. Accounts are created by an administrator.",
    points: [
      { icon: Activity, text: "Live incidents and SOS alerts as they arrive" },
      { icon: MapPinned, text: "Risk levels and the nearest units on one map" },
      {
        icon: FileClock,
        text: "Every action is recorded in a tamper-evident audit log",
      },
    ],
    formTitle: "Staff log in",
  },
};

const ROLE_OPTIONS: {
  kind: SessionKind;
  label: string;
  icon: typeof Compass;
}[] = [
  { kind: "tourist", label: "Tourist", icon: Compass },
  { kind: "staff", label: "Authority", icon: Building2 },
];

// Where each kind of account goes after logging in.
const HOME_SECTION: Record<SessionKind, string> = {
  tourist: "tourist",
  staff: "dashboard",
};

type Props = {
  initialKind?: SessionKind;
  initialRegistering?: boolean;
};

export default function LoginForm({ initialKind = "tourist", initialRegistering = false }: Props) {
  const [kind, setKind] = useState<SessionKind>(initialKind);
  const [registering, setRegistering] = useState(initialRegistering && initialKind === "tourist");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();
  const copy = COPY[kind];

  function chooseKind(next: SessionKind) {
    setKind(next);
    setError(null);
    if (next === "staff") setRegistering(false); // staff cannot create their own accounts
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (registering) {
        await apiRequest("POST", "/auth/register", {
          body: { email, password, full_name: fullName },
        });
      }
      const session = await login(email, password);
      const isStaff = STAFF_ROLES.includes(session.user.role);
      if (kind === "tourist" && isStaff) {
        setError("This is a staff account. Move the switch above to Authority.");
      } else if (kind === "staff" && !isStaff) {
        setError("This is a tourist account. Move the switch above to Tourist.");
      } else {
        setSession(kind, session);
        window.location.hash = link(HOME_SECTION[kind]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="auth-top">
        <a className="back-link" href={link()}>
          <ArrowLeft aria-hidden="true" />
          Back to home
        </a>
      </div>
      <div className="auth">
        <aside className="auth-aside">
          <div>
            <h1>{copy.title}</h1>
            <p>{copy.lead}</p>
          </div>
          <ul className="auth-points">
            {copy.points.map(({ icon: Icon, text }) => (
              <li key={text}>
                <Icon aria-hidden="true" />
                {text}
              </li>
            ))}
          </ul>
        </aside>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="role-switch" role="group" aria-label="Log in as" data-active={kind}>
            <span className="role-switch-thumb" aria-hidden="true" />
            {ROLE_OPTIONS.map(({ kind: option, label, icon: Icon }) => (
              <button
                key={option}
                type="button"
                aria-pressed={kind === option}
                onClick={() => chooseKind(option)}
              >
                <Icon aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          <h2>{registering ? "Create your tourist account" : copy.formTitle}</h2>

          {registering && (
            <div className="field">
              <label className="field-label" htmlFor={`${id}-name`}>
                Full name
              </label>
              <input
                id={`${id}-name`}
                className="input"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
          )}
          <div className="field">
            <label className="field-label" htmlFor={`${id}-email`}>
              E-mail
            </label>
            <input
              id={`${id}-email`}
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor={`${id}-password`}>
              Password
            </label>
            <div className="input-group">
              <input
                id={`${id}-password`}
                className="input"
                type={showPassword ? "text" : "password"}
                autoComplete={registering ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={registering ? 10 : undefined}
                aria-describedby={registering ? `${id}-password-hint` : undefined}
                required
              />
              <button
                type="button"
                className="btn btn-secondary btn-icon"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
              </button>
            </div>
            {registering && (
              <span className="field-hint" id={`${id}-password-hint`}>
                At least 10 characters.
              </span>
            )}
          </div>

          {error && (
            <Notice tone="danger" live="alert">
              {error}
            </Notice>
          )}

          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Please wait…" : registering ? "Create account" : "Log in"}
          </button>

          {kind === "tourist" ? (
            <p className="auth-switch">
              {registering ? "Already have an account?" : "New to TSMIRP?"}{" "}
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setRegistering(!registering);
                  setError(null);
                }}
              >
                {registering ? "Log in" : "Create a tourist account"}
              </button>
            </p>
          ) : (
            <p className="auth-switch">Staff accounts are created by an administrator.</p>
          )}

          <p className="muted small row">
            <ShieldCheck aria-hidden="true" width={16} height={16} />
            Passwords are stored only as a secure hash.
          </p>
        </form>
      </div>
    </>
  );
}
