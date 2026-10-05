"use client";

import { useEffect, useState } from "react";
import { api, CurrentUser } from "@/lib/api";
import { Pagination } from "@/components/pagination";
import { OrganizationSettings } from "@/components/organization-settings";
import { InfrastructureSettings } from "@/components/infrastructure-settings";

export default function Administration() {
  const [page, setPage] = useState(0);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [accounts, setAccounts] = useState<CurrentUser[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Exclude<CurrentUser["role"], "owner">>("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api<CurrentUser>("/auth/me").then(user => {
      const admin = ["owner", "admin"].includes(user.role);
      setAllowed(admin);
      if (admin) api<CurrentUser[]>(`/administration/accounts?limit=50&offset=${page*50}`).then(setAccounts)
        .catch(e => setError(e instanceof Error ? e.message : "Unable to load accounts"));
    }).catch(e => { setAllowed(false); setError(e instanceof Error ? e.message : "Unable to load administration"); });
  }, [page]);

  async function createAccount(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setSuccess("");
    try {
      const account = await api<CurrentUser>("/administration/accounts", { method: "POST", body: JSON.stringify({ email: email.trim(), role }) });
      setAccounts(previous => [...previous, account].sort((a, b) => a.email.localeCompare(b.email)));
      setSuccess(`Account created. Invitation email queued for ${account.email}.`);
      setEmail(""); setRole("member");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create account"); }
    finally { setBusy(false); }
  }

  async function updateAccount(account: CurrentUser, changes: object) {
    setBusy(true); setError("");
    try {
      const updated = await api<CurrentUser>(`/administration/accounts/${account.id}`, {method: "PATCH", body: JSON.stringify(changes)});
      setAccounts(previous => previous.map(item => item.id === account.id ? updated : item));
      setSuccess("Account updated. Existing sessions revoked.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to update account"); }
    finally { setBusy(false); }
  }

  if (allowed === null) return <div className="page"><p role="status">Loading administration…</p></div>;
  if (!allowed) return <div className="page"><h1 className="page-title">Administration</h1><p role="alert">Only administrators can access this page.</p>{error && <p className="error-text">{error}</p>}</div>;

  return <div className="page" style={{ maxWidth: 860 }}>
    <header className="page-head"><div><h1 className="page-title">Administration</h1><p className="page-description">Manage accounts, organization profile, and self-hosted infrastructure.</p></div></header>
    <section style={{ padding: "18px 0 28px", borderTop: "1px solid var(--line)" }}>
      <h2 className="section-heading">Create account</h2>
      <p className="page-description" style={{ marginBottom: 20 }}>Enter an email and role. An expiring invitation link lets the recipient choose a password. Configure SMTP below before creating accounts.</p>
      <form className="setup-form" onSubmit={createAccount}>
        <div className="setup-grid">
          <label className="field"><span>Email</span><input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required maxLength={320} disabled={busy} /></label>
          <label className="field"><span>Role</span><select value={role} onChange={event => setRole(event.target.value as Exclude<CurrentUser["role"], "owner">)} disabled={busy}><option value="member">Member</option><option value="admin">Administrator</option><option value="accountant">Accountant</option><option value="approver">Approver</option><option value="viewer">Viewer</option></select></label>
        </div>
        <button className="button button-primary" style={{ marginTop: 12 }} disabled={busy}>{busy ? "Creating & sending…" : "Create account"}</button>
      </form>
      {error && <p className="error-text" role="alert">{error}</p>}
      {success && <p className="notice" role="status">{success}</p>}
      <h2 className="section-heading" style={{ marginTop: 28 }}>Accounts</h2>
      <div className="table-wrap"><table><thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{accounts.map(account => <tr key={account.id}><td>{account.full_name}</td><td>{account.email}</td><td>{account.role === "owner" ? "Owner" : <select aria-label={`Role for ${account.email}`} disabled={busy} value={account.role} onChange={event => updateAccount(account, {role: event.target.value})}>{["admin", "accountant", "approver", "member", "viewer"].map(role => <option key={role} value={role}>{role}</option>)}</select>}</td><td>{account.invitation_pending ? "Invitation pending" : account.membership_active ? "Active" : "Disabled"}</td><td>{account.role !== "owner" && <><button className="button" disabled={busy} onClick={() => updateAccount(account, {is_active: !account.membership_active})}>{account.membership_active ? "Disable" : "Enable membership"}</button><button className="button" disabled={busy} onClick={() => updateAccount(account, {revoke_sessions: true})}>Revoke sessions</button>{account.invitation_pending && account.membership_active && <button className="button" disabled={busy} onClick={async () => {setBusy(true); setError(""); try {await api(`/administration/accounts/${account.id}/invite`, {method: "POST"}); setSuccess("New invitation queued. Previous links revoked.");} catch (e) {setError(e instanceof Error ? e.message : "Unable to renew invitation");} finally {setBusy(false);}}}>Renew invitation</button>}</>}</td></tr>)}</tbody></table></div>
    </section>
    <Pagination page={page} count={accounts.length} busy={busy} onPage={setPage}/>
    <OrganizationSettings />
    <InfrastructureSettings />
  </div>;
}
