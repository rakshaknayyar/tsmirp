// Log-in form, optionally with a "create account" mode (tourists only).
// The token is kept in memory only (React state), so reloading the page logs you out.

import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest, login } from "./api";
import type { Session } from "./types";

type Props = {
  title: string;
  allowRegister?: boolean;
  onLoggedIn: (session: Session) => void;
};

export default function LoginForm({ title, allowRegister = false, onLoggedIn }: Props) {
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      onLoggedIn(await login(email, password));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 8, maxWidth: 360 }}>
      <h2>{registering ? "Create tourist account" : title}</h2>
      {registering && (
        <input
          placeholder="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
        />
      )}
      <input
        type="email"
        placeholder="E-mail"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder={registering ? "Password (at least 10 characters)" : "Password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        minLength={registering ? 10 : undefined}
        required
      />
      <button type="submit" disabled={busy}>
        {registering ? "Create account" : "Log in"}
      </button>
      {allowRegister && (
        <button type="button" onClick={() => setRegistering(!registering)}>
          {registering ? "I already have an account" : "Create a tourist account"}
        </button>
      )}
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
