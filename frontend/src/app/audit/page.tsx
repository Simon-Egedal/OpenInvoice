"use client";

import { useEffect, useState } from "react";
import { api, CurrentUser } from "@/lib/api";

type Event = { id: string; action: string; entity_type: string; entity_id: string; created_at: string; new_values: Record<string, unknown> | null };

export default function Audit() {
  const [rows, setRows] = useState<Event[]>([]);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<CurrentUser>("/auth/me").then(async user => {
      const admin = ["owner", "admin"].includes(user.role);
      setAllowed(admin);
      if (admin) setRows(await api<Event[]>("/audit"));
    }).catch(e => setError(e instanceof Error ? e.message : "Unable to load activity"))
      .finally(() => setLoading(false));
  }, []);

  if (allowed === false) return <div className="page"><h1 className="page-title">Activity</h1><p role="alert">Only administrators can access this page.</p></div>;
  if (loading) return <div className="page"><p role="status">Loading activity…</p></div>;

  return <div className="page">
    <header className="page-head"><div><h1 className="page-title">Activity</h1><p className="page-description">A record of important changes in your organization.</p></div></header>
    {error ? <p className="error-text" role="alert">{error}</p> : rows.length === 0 ? <div className="empty">No activity recorded yet.</div> :
      <div className="table-wrap"><table><thead><tr><th scope="col">Event</th><th scope="col">Details</th><th scope="col">Time</th></tr></thead><tbody>{rows.map(x => <tr key={x.id}><td className="td-strong">{x.action.replaceAll(".", " · ")}</td><td>{String(x.new_values?.name ?? x.new_values?.invoice_number ?? x.entity_type)}</td><td>{new Date(x.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
  </div>;
}
