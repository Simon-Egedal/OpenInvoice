"use client";
import { useEffect, useState } from "react";
import { API, api, CurrentUser } from "@/lib/api";

export default function DataTransfer() {
  const [kind, setKind] = useState("customers");
  const [file, setFile] = useState<File | null>(null);
  const [canWrite, setCanWrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => { api<CurrentUser>("/auth/me").then(user => setCanWrite(["owner", "admin", "member", "accountant"].includes(user.role))).catch(e => setError(e.message)); }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (!file) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const body = new FormData(); body.append("document", file);
      const response = await fetch(`${API}/api/v1/imports/${kind}`, {method: "POST", credentials: "include", body});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Import failed");
      setMessage(`${result.imported} records imported.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed"); }
    finally { setBusy(false); }
  }
  return <div className="page"><header className="page-head"><div><h1 className="page-title">Import and export</h1><p className="page-description">Download financial records or import customers and products.</p></div></header>
    <h2 className="section-heading">Exports</h2><div className="row-actions"><a className="button" href={`${API}/api/v1/exports/invoices.csv`}>Export invoices</a><a className="button" href={`${API}/api/v1/exports/payments.csv`}>Export payments and allocations</a></div>
    {canWrite && <><h2 className="section-heading">CSV import</h2><p>Use UTF-8 CSV, up to 1,000 records and 2 MB. Duplicate names are rejected. Each import succeeds completely or saves no records.</p><form onSubmit={submit} className="setup-form"><label className="field"><span>Record type</span><select value={kind} onChange={e => setKind(e.target.value)}><option value="customers">Customers</option><option value="products">Products</option></select></label><a className="text-link" href={`${API}/api/v1/imports/${kind}/template.csv`}>Download CSV template</a><label className="field"><span>CSV file</span><input type="file" accept=".csv,text/csv" required onChange={e => setFile(e.target.files?.[0] ?? null)}/></label><button className="button button-primary" disabled={busy || !file}>{busy ? "Importing…" : "Import records"}</button></form></>}
    {error && <p className="error-text" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
  </div>;
}
