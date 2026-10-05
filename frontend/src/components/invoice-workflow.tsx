"use client";
import { useCallback, useEffect, useState, useRef } from "react";
import { API, api, CurrentUser, Invoice } from "@/lib/api";

type Document = {id: string; filename: string};
type Decision = {id: string; decision: string; reason: string | null; created_at: string};
type Delivery = {id: string; kind: string; status: string; recipient: string; failed_attempts: number; error_message: string | null; created_at: string};

export function InvoiceWorkflow({invoice, onChange}: {invoice: Invoice; onChange: () => Promise<void>}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [role, setRole] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const actionKeys = useRef<Record<string, string>>({});
  const actionBusy = useRef(false);
  const canWrite = ["owner", "admin", "accountant", "member"].includes(role);
  const canApprove = ["owner", "admin", "approver"].includes(role);
  const load = useCallback(async () => {
    try {
      const [docs, history, emails, user] = await Promise.all([api<Document[]>(`/invoices/${invoice.id}/documents`), api<Decision[]>(`/invoices/${invoice.id}/decisions`), api<Delivery[]>(`/invoices/${invoice.id}/deliveries`), api<CurrentUser>("/auth/me")]);
      setDocuments(docs); setDecisions(history); setDeliveries(emails); setRole(user.role);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load workflow history"); }
  }, [invoice.id]);
  useEffect(() => { void load(); }, [load, invoice]);
  useEffect(() => {
    if (!deliveries.some(delivery => ["queued", "sending", "failed"].includes(delivery.status))) return;
    const timer = setInterval(() => { void load(); }, 10000);
    return () => clearInterval(timer);
  }, [deliveries, load]);
  async function action(path: string, body?: object) {
    if (actionBusy.current) return;
    actionBusy.current = true;
    actionKeys.current[path] ??= crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await api(path, {method: "POST", headers: {"Idempotency-Key": actionKeys.current[path]}, body: body ? JSON.stringify(body) : undefined});
      delete actionKeys.current[path];
      setMessage("Action saved."); setReason("");
      await onChange(); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { actionBusy.current = false; setBusy(false); }
  }
  return <section style={{margin: "24px 0"}}>
    <h2 className="section-heading">Invoice workflow</h2>
    <div className="row-actions">
      {canWrite && invoice.invoice_type === "outgoing" && invoice.status === "draft" && <button className="button" disabled={busy} onClick={() => action(`/invoices/${invoice.id}/issue`)}>Issue invoice</button>}
      {canWrite && invoice.invoice_type === "outgoing" && invoice.is_overdue && <button className="button" disabled={busy} onClick={() => action(`/invoices/${invoice.id}/reminders`)}>Send payment reminder</button>}
      {canWrite && invoice.invoice_type === "incoming" && ["received", "rejected"].includes(invoice.status) && <button className="button" disabled={busy} onClick={() => action(`/invoices/${invoice.id}/approval`, {decision: "pending_approval"})}>Submit for approval</button>}
      {canApprove && invoice.status === "pending_approval" && <><button className="button" disabled={busy} onClick={() => action(`/invoices/${invoice.id}/approval`, {decision: "approved", reason: reason || null})}>Approve</button><label className="field"><span>Decision reason</span><input value={reason} maxLength={2000} onChange={e => setReason(e.target.value)}/></label><button className="button" disabled={busy || !reason.trim()} onClick={() => action(`/invoices/${invoice.id}/approval`, {decision: "rejected", reason})}>Reject</button></>}
    </div>
    {message && <p role="status">{message}</p>}
    {error && <p className="error-text" role="alert">{error} <button className="button" onClick={load}>Retry loading</button></p>}
    {documents.length > 0 && <><h3>Original documents</h3><ul>{documents.map(doc => <li key={doc.id}><a className="text-link" href={`${API}/api/v1/invoices/${invoice.id}/documents/${doc.id}`}>{doc.filename}</a></li>)}</ul></>}
    {decisions.length > 0 && <><h3>Approval history</h3><ul>{decisions.map(item => <li key={item.id}>{item.decision.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleString()}{item.reason ? ` · ${item.reason}` : ""}</li>)}</ul></>}
    <h3>Email and reminders</h3>
    {deliveries.length === 0 ? <p>No deliveries yet.</p> : <div className="table-wrap"><table><thead><tr><th>Type</th><th>Recipient</th><th>Status</th><th>Attempts failed</th><th>Action</th></tr></thead><tbody>{deliveries.map(item => <tr key={item.id}><td>{item.kind}</td><td>{item.recipient}</td><td>{item.status}{item.error_message && <div>{item.error_message}</div>}</td><td>{item.failed_attempts}</td><td>{canWrite && ["failed", "uncertain"].includes(item.status) && <button className="button" disabled={busy} onClick={() => { if (item.status !== "uncertain" || confirm("Delivery may already have reached the recipient. Retry only after verifying receipt. Send again?")) void action(`/invoices/${invoice.id}/deliveries/${item.id}/retry`); }}>Retry delivery</button>}</td></tr>)}</tbody></table></div>}
  </section>;
}
