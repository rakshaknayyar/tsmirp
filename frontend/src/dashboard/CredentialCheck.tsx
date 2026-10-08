// Check a digital tourist ID (POST /credential/verify). In a real deployment a scanner would
// read the QR code; in this prototype the operator pastes the text inside it.

import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";

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

  async function check(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    try {
      const verification = await apiRequest<Verification>("POST", "/credential/verify", {
        token,
        body: { token: credential.trim() },
      });
      setResult(verification);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <h2>Check a digital tourist ID</h2>
      <form onSubmit={check} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
        <textarea
          placeholder="Paste the text inside the tourist's QR code"
          value={credential}
          onChange={(e) => setCredential(e.target.value)}
          rows={3}
          minLength={10}
          required
        />
        <button type="submit">Check</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {result && (
        <p role="status" style={{ color: result.valid ? "#2e7d32" : "#c62828" }}>
          <strong>{result.valid ? "Genuine" : "Not valid"}:</strong> {result.reason}
          {result.valid &&
            ` - ${result.full_name} (tourist #${result.user_id}` +
              `${result.nationality ? `, ${result.nationality}` : ""}), valid until ` +
              `${new Date(result.expires_at!).toLocaleDateString()}`}
        </p>
      )}
    </section>
  );
}
