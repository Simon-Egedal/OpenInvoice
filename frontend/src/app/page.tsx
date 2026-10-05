"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { api, Invoice } from "@/lib/api";
import { InvoiceTable } from "@/components/data-table";
import { formatMoney } from "@/lib/money";

type Aging = {
  invoice_type: "incoming" | "outgoing"; currency: string; outstanding: string;
  overdue: string; paid: string; current: string; days_1_30: string;
  days_31_60: string; days_61_90: string; days_91_plus: string;
};

export default function Overview() {
  const [items, setItems] = useState<Invoice[]>([]);
  const [groups, setGroups] = useState<Aging[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  async function load() {
    setLoading(true); setError("");
    try {
      const [invoices, aging] = await Promise.all([api<Invoice[]>("/invoices?limit=6"), api<Aging[]>("/reports/aging")]);
      setItems(invoices); setGroups(aging);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load overview"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  const names = Object.fromEntries(items.map(invoice => [invoice.customer_id ?? invoice.supplier_id ?? "", invoice.recipient_name ?? ""]));
  return <div className="page">
    <header className="page-head"><div><h1 className="page-title">Overview</h1><p className="page-description">Balances by invoice direction and currency.</p></div><Link className="button button-primary" href="/invoices/new"><Plus size={15}/>New invoice</Link></header>
    {error && <p className="error-text" role="alert">{error} <button className="button" onClick={load}>Retry</button></p>}
    {loading && <p role="status">Loading overview…</p>}
    {!loading && !error && groups.length === 0 && <p>No issued invoices yet. Create and issue an invoice to see balances.</p>}
    {groups.map(group => <section key={`${group.invoice_type}-${group.currency}`}>
      <h2 className="section-heading">{group.invoice_type === "outgoing" ? "Receivables" : "Payables"} · {group.currency}</h2>
      <div className="metrics">{([ ["Outstanding", group.outstanding], ["Overdue", group.overdue], ["Payments recorded", group.paid] ] as const).map(([label, value]) => <div className="metric" key={label}><div className="metric-label">{label}</div><div className="metric-value">{group.currency} {formatMoney(value)}</div></div>)}</div>
      <div className="table-wrap"><table><caption className="sr-only">Aging balances in {group.currency}</caption><thead><tr>{["Not overdue", "1–30 days", "31–60 days", "61–90 days", "91+ days"].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody><tr>{[group.current, group.days_1_30, group.days_31_60, group.days_61_90, group.days_91_plus].map((value, index) => <td className="mono" key={index}>{formatMoney(value)}</td>)}</tr></tbody></table></div>
    </section>)}
    <div className="section-heading"><span>Recent invoices</span><Link className="text-link" href="/invoices">View all</Link></div>
    <InvoiceTable items={items} partyNames={names}/>
  </div>;
}
