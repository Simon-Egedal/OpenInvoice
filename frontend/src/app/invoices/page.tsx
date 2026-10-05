"use client";
import Link from "next/link";
import { useState } from "react";
import { Invoice } from "@/lib/api";
import { InvoiceTable } from "@/components/data-table";
import { Pagination } from "@/components/pagination";
import { usePagedRecords } from "@/lib/use-paged-records";

export default function Invoices() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [kind, setKind] = useState("all");
  const records = usePagedRecords<Invoice>("/invoices", `&q=${encodeURIComponent(q)}${status === "all" ? "" : `&status=${status}`}${kind === "all" ? "" : `&invoice_type=${kind}`}`);
  const names = Object.fromEntries(records.items.map(invoice => [invoice.customer_id ?? invoice.supplier_id ?? "", invoice.recipient_name ?? ""]));
  return <div className="page"><header className="page-head"><div><h1 className="page-title">Invoices</h1><p className="page-description">Create, send and track incoming and outgoing invoices.</p></div><div className="row-actions"><Link className="button" href="/invoices/receive">Receive PDF</Link><Link className="button button-primary" href="/invoices/new">New invoice</Link></div></header>
    <div className="toolbar"><input className="search" aria-label="Search invoices" placeholder="Search invoice number or party…" value={q} onChange={e => {setQ(e.target.value); records.setPage(0);}}/><select className="filter" aria-label="Invoice direction" value={kind} onChange={e => {setKind(e.target.value); records.setPage(0);}}><option value="all">Incoming and outgoing</option><option value="outgoing">Outgoing</option><option value="incoming">Incoming</option></select><select className="filter" aria-label="Filter by status" value={status} onChange={e => {setStatus(e.target.value); records.setPage(0);}}><option value="all">All statuses</option>{["draft", "issued", "received", "pending_approval", "approved", "sent", "partially_paid", "paid", "overdue", "cancelled", "rejected"].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></div>
    {records.error && <p className="error-text" role="alert">{records.error} <button className="button" onClick={() => records.load()}>Retry</button></p>}
    {records.loading && <p role="status">Loading invoices…</p>}
    <InvoiceTable items={records.items} partyNames={names}/><Pagination page={records.page} count={records.items.length} busy={records.loading} onPage={records.setPage}/>
  </div>;
}
