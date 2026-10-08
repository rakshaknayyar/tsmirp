// Digital tourist ID: a signed, time-limited credential shown as a QR code
// (GET /tourist/credential). Staff can check it on the dashboard. It replaces the blockchain ID
// of the problem statement, which is out of scope for this prototype.

import { useState } from "react";

import { apiGet } from "../shared/api";

type Credential = {
  token: string;
  issued_at: string;
  expires_at: string;
  qr_svg: string;
  note: string;
};

export default function CredentialPanel({ token }: { token: string }) {
  const [credential, setCredential] = useState<Credential | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function show() {
    setError(null);
    try {
      setCredential(await apiGet<Credential>("/tourist/credential", token));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <h2>Digital tourist ID</h2>
      <button onClick={show}>{credential ? "Get a fresh ID" : "Show my ID (QR code)"}</button>
      {error && <p role="alert">{error}</p>}
      {credential && (
        <div>
          <img
            // The SVG comes from our own API; as an <img> it cannot run scripts.
            src={`data:image/svg+xml;utf8,${encodeURIComponent(credential.qr_svg)}`}
            alt="QR code of my digital tourist ID"
            style={{ width: 220, maxWidth: "100%", background: "#fff", display: "block" }}
          />
          <p style={{ margin: "4px 0" }}>
            Valid until {new Date(credential.expires_at).toLocaleDateString()}
          </p>
          <p style={{ fontSize: 12, margin: 0 }}>{credential.note}</p>
          <details style={{ fontSize: 12 }}>
            <summary>Show the text inside the QR code</summary>
            <code style={{ wordBreak: "break-all" }}>{credential.token}</code>
          </details>
        </div>
      )}
    </section>
  );
}
