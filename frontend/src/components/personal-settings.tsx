"use client";

import { useEffect, useState } from "react";
import { api, CurrentUser } from "@/lib/api";

export function PersonalSettings() {
  const [name, setName] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api<CurrentUser>("/auth/me").then(user => { setName(user.full_name); setLoaded(true); })
      .catch(e => setError(e instanceof Error ? e.message : "Unable to load profile"));
  }, []);

  async function save(event: React.FormEvent, kind: "name" | "password") {
    event.preventDefault();
    setError(""); setSuccess("");
    if (kind === "password" && password !== confirmation) { setError("New passwords must match."); return; }
    setBusy(true);
    try {
      if (kind === "name") {
        const user = await api<Pick<CurrentUser, "id" | "email" | "full_name">>("/auth/profile", { method: "PATCH", body: JSON.stringify({ full_name: name.trim() }) });
        setName(user.full_name);
        window.dispatchEvent(new Event("profileUpdated"));
        setSuccess("Name updated.");
      } else {
        await api<void>("/auth/password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: password }) });
        setCurrentPassword(""); setPassword(""); setConfirmation("");
        setSuccess("Password changed.");
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to save changes"); }
    finally { setBusy(false); }
  }

  return <section style={{ padding: "18px 0 28px", borderTop: "1px solid var(--line)" }}>
    <h2 className="section-heading">Your account</h2>
    <form className="setup-form personal-settings-form" onSubmit={event => save(event, "name")}>
      <label className="field"><span>Name</span><input autoComplete="name" value={name} onChange={event => setName(event.target.value)} required maxLength={200} disabled={!loaded || busy} /></label>
      <button className="button button-primary" disabled={!loaded || busy || !name.trim()}>Save name</button>
    </form>
    <h2 className="section-heading" style={{ marginTop: 28 }}>Change password</h2>
    <form className="setup-form personal-settings-form" onSubmit={event => save(event, "password")}>
      <label className="field"><span>Current password</span><input type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} required disabled={busy} /></label>
      <label className="field"><span>New password</span><input type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required minLength={12} maxLength={256} disabled={busy} /></label>
      <p className="setup-hint">Use at least 12 characters.</p>
      <label className="field"><span>Confirm new password</span><input type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} required minLength={12} maxLength={256} disabled={busy} /></label>
      <button className="button button-primary" disabled={!loaded || busy}>Change password</button>
    </form>
    {error && <p className="error-text" role="alert">{error}</p>}
    {success && <p className="notice" role="status">{success}</p>}
  </section>;
}
