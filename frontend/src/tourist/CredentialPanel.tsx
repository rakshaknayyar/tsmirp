// Digital tourist ID: a signed, time-limited credential (GET /tourist/credential) shown as a
// card with a QR code. The QR code is HIDDEN until the tourist chooses to show it, and hides
// itself again after a minute, so it is not left on screen for anyone to photograph.
// It replaces the blockchain ID of the problem statement, which is out of scope.

import { Eye, EyeOff, Landmark, LockKeyhole, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { apiGet } from "../shared/api";
import { formatDate } from "../shared/format";
import { link } from "../shared/router";
import type { Profile, User } from "../shared/types";
import { Notice, Panel } from "../shared/ui";

type Credential = {
  token: string;
  issued_at: string;
  expires_at: string;
  qr_svg: string;
  note: string;
};

const AUTO_HIDE_SECONDS = 60;

type Props = { token: string; user: User; profile: Profile | null };

export default function CredentialPanel({ token, user, profile }: Props) {
  const [credential, setCredential] = useState<Credential | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hide the QR code again after a minute.
  useEffect(() => {
    if (!revealed) return;
    const timer = window.setTimeout(() => setRevealed(false), AUTO_HIDE_SECONDS * 1000);
    return () => window.clearTimeout(timer);
  }, [revealed, credential]);

  async function fetchCredential(): Promise<boolean> {
    setError(null);
    setBusy(true);
    try {
      setCredential(await apiGet<Credential>("/tourist/credential", token));
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function show() {
    if (credential || (await fetchCredential())) setRevealed(true);
  }

  return (
    <div className="stack-lg">
      <section className="id-card" aria-label="Digital tourist ID">
        <div>
          <div className="id-card-top">
            <Landmark aria-hidden="true" />
            Digital tourist ID, Jaipur
          </div>
          <p className="id-card-name">{user.full_name}</p>
          <dl className="id-card-meta">
            <div>
              <dt>Nationality</dt>
              <dd>{profile?.nationality || "Not added yet"}</dd>
            </div>
            <div>
              <dt>Tourist number</dt>
              <dd>{user.id}</dd>
            </div>
            <div>
              <dt>Valid until</dt>
              <dd>{credential ? formatDate(credential.expires_at) : "Shown with the QR code"}</dd>
            </div>
          </dl>
          <div className="id-card-stripe" aria-hidden="true" />
        </div>

        {revealed && credential ? (
          <div className="stack">
            <div className="id-qr">
              <img
                // The SVG comes from our own API; as an <img> it cannot run scripts.
                src={`data:image/svg+xml;utf8,${encodeURIComponent(credential.qr_svg)}`}
                alt="QR code of your digital tourist ID"
              />
            </div>
            <button className="btn btn-on-dark-ghost btn-sm" onClick={() => setRevealed(false)}>
              <EyeOff aria-hidden="true" />
              Hide QR code
            </button>
          </div>
        ) : (
          <div className="id-qr id-qr-hidden">
            <LockKeyhole aria-hidden="true" />
            <span>Your QR code is hidden</span>
            <button className="btn btn-on-dark btn-sm" onClick={() => void show()} disabled={busy}>
              <Eye aria-hidden="true" />
              {busy ? "Loading…" : "Show QR code"}
            </button>
          </div>
        )}
      </section>

      {error && (
        <Notice tone="danger" live="alert">
          {error}
        </Notice>
      )}

      <Panel
        title="About your ID"
        description="Show the QR code when police or tourism staff ask for identification. They can check that it is genuine and not expired."
        actions={
          <button className="btn btn-secondary btn-sm" onClick={() => void fetchCredential()} disabled={busy}>
            <RefreshCw aria-hidden="true" />
            Get a new ID
          </button>
        }
      >
        <ul className="simulated-list">
          <li>
            <strong>What it contains</strong>
            Your name, nationality and the dates it is valid. Never your location or phone number.
          </li>
          <li>
            <strong>Hidden by default</strong>
            The QR code hides itself again after {AUTO_HIDE_SECONDS} seconds.
          </li>
          <li>
            <strong>Valid for 30 days</strong>
            Get a new one at any time, for example after updating your{" "}
            <a href={link("tourist", "profile")}>nationality</a>.
          </li>
        </ul>
        {revealed && credential && (
          <details className="mt-md">
            <summary className="small">Show the text inside the QR code</summary>
            <p className="token-box mt-xs">
              {credential.token}
            </p>
          </details>
        )}
      </Panel>
    </div>
  );
}
