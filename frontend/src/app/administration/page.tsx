"use client";

import { useEffect, useState } from "react";
import { api, CurrentUser } from "@/lib/api";
import { OrganizationSettings } from "@/components/organization-settings";
import { InfrastructureSettings } from "@/components/infrastructure-settings";

export default function Administration() {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [accounts, setAccounts] = useState<CurrentUser[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "admin">("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api<CurrentUser>("/auth/me").then(user => {
      const admin = ["owner", "admin"].includes(user.role);
      setAllowed(admin);
      if (admin) api<CurrentUser[]>("/administration/accounts").then(setAccounts)
        .catch(e => setError(e instanceof Error ? e.message : "Unable to load accounts"));
    }).catch(e => { setAllowed(false); setError(e instanceof Error ? e.message : "Unable to load administration"); });
  }, []);

  async function createAccount(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setSuccess("");
    try {
      const account = await api<CurrentUser>("/administration/accounts", { method: "POST", body: JSON.stringify({ email: email.trim(), role }) });
      setAccounts(previous => [...previous, account].sort((a, b) => a.email.localeCompare(b.email)));
      setSuccess(`Account created. Login credentials emailed to ${account.email}.`);
      setEmail(""); setRole("member");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create account"); }
    finally { setBusy(false); }
  }

  if (allowed === null) return <div className="page"><p role="status">Loading administration…</p></div>;
  if (!allowed) return <div className="page"><h1 className="page-title">Administration</h1><p role="alert">Only administrators can access this page.</p>{error && <p className="error-text">{error}</p>}</div>;

  return <div className="page" style={{ maxWidth: 860 }}>
    <header className="page-head"><div><h1 className="page-title">Administration</h1><p className="page-description">Manage accounts, organization profile, and self-hosted infrastructure.</p></div></header>
    <section style={{ padding: "18px 0 28px", borderTop: "1px solid var(--line)" }}>
      <h2 className="section-heading">Create account</h2>
      <p className="page-description" style={{ marginBottom: 20 }}>Enter an email and role. A password is generated automatically and emailed to the recipient. Configure SMTP below before creating accounts.</p>
      <form className="setup-form" onSubmit={createAccount}>
        <div className="setup-grid">
          <label className="field"><span>Email</span><input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required maxLength={320} disabled={busy} /></label>
          <label className="field"><span>Role</span><select value={role} onChange={event => setRole(event.target.value as "member" | "admin")} disabled={busy}><option value="member">Member</option><option value="admin">Administrator</option></select></label>
        </div>
        <button className="button button-primary" disabled={busy}>{busy ? "Creating & sending…" : "Create account"}</button>
      </form>
      {error && <p className="error-text" role="alert">{error}</p>}
      {success && <p className="notice" role="status">{success}</p>}
      <h2 className="section-heading" style={{ marginTop: 28 }}>Accounts</h2>
      <div className="table-wrap"><table><thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Role</th></tr></thead><tbody>{accounts.map(account => <tr key={account.id}><td>{account.full_name}</td><td>{account.email}</td><td>{["admin", "owner"].includes(account.role) ? "Administrator" : account.role}</td></tr>)}</tbody></table></div>
    </section>
    <OrganizationSettings />
    <InfrastructureSettings />
  </div>;
}
