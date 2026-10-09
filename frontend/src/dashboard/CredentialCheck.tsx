// Check a digital tourist ID (POST /credential/verify). In a real deployment a scanner would
// read the QR code; in this prototype the operator pastes the text inside it.

import { ScanLine } from "lucide-react";
import { useId, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";
import { formatDate } from "../shared/format";
import { Field, Notice, Panel } from "../shared/ui";

type Verification = {
  valid: boolean;
  reason: string;
  user_id: number | null;
  full_name: string | null;
  nationality: string | null;
  expires_at: string | null;
};

export default function CredentialCheck({ token }: { token: string }) {
  const [credential, setCredential] = useState("");
  const [result, setResult] = useState<Verification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function check(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const verification = await apiRequest<Verification>("POST", "/credential/verify", {
        token,
        body: { token: credential.trim() },
      });
      setResult(verification);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Check a digital tourist ID"
      description="Paste the text inside the tourist's QR code (in the tourist app: My ID, then 'Show the text inside the QR code'). Every check is recorded in the audit log."
    >
      <form className="stack narrow" onSubmit={check}>
        <Field id={`${id}-token`} label="Text inside the QR code">
          <textarea
            id={`${id}-token`}
            className="textarea"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
            rows={4}
            minLength={10}
            spellCheck={false}
            required
          />
        </Field>
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            <ScanLine aria-hidden="true" />
            {busy ? "Checking…" : "Check ID"}
          </button>
        </div>
        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}
        {result &&
          (result.valid ? (
            <Notice tone="success" live="status" title="Genuine ID">
              {result.full_name}, tourist #{result.user_id}
              {result.nationality ? `, ${result.nationality}` : ""}. Valid until{" "}
              {formatDate(result.expires_at!)}.
            </Notice>
          ) : (
            <Notice tone="danger" live="alert" title="Not a valid ID">
              {result.reason}
            </Notice>
          ))}
      </form>
    </Panel>
  );
}
