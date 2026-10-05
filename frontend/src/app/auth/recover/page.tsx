"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function AccountRecovery() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    setToken(window.location.hash.slice(1));
    // Tokens stay out of request URLs and browser history after the page loads.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(""); setMessage("");
    if (token && password !== confirmation) { setError("Passwords must match."); return; }
    setBusy(true);
    try {
      if (token) {
        await api("/auth/consume-link", {method: "POST", body: JSON.stringify({token, password})});
        setMessage("Password saved. Sign in with your new password.");
        setPassword(""); setConfirmation("");
      } else {
        const result = await api<{message: string}>("/auth/reset-password", {method: "POST", body: JSON.stringify({email})});
        setMessage(result.message);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to process account recovery"); }
    finally { setBusy(false); }
  }
  return <div className="page" style={{maxWidth: 520, paddingTop: 75}}><h1 className="page-title">{token ? "Set your password" : "Reset password"}</h1><form className="form-grid" onSubmit={submit}>
    {token ? <><label className="field full"><span>New password</span><input type="password" autoComplete="new-password" required minLength={12} maxLength={256} value={password} onChange={e => setPassword(e.target.value)}/></label><label className="field full"><span>Confirm password</span><input type="password" autoComplete="new-password" required minLength={12} maxLength={256} value={confirmation} onChange={e => setConfirmation(e.target.value)}/></label></> : <label className="field full"><span>Email</span><input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)}/></label>}
    <button className="button button-primary" disabled={busy}>{busy ? "Saving…" : token ? "Save password" : "Send reset link"}</button>
  </form>{error && <p className="error-text" role="alert">{error}</p>}{message && <p role="status">{message}</p>}<Link className="text-link" href="/auth">Back to sign in</Link></div>;
}
