"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Plus } from "lucide-react";
import { api, Invoice, Organization, Party } from "@/lib/api";
import { InvoiceTable } from "@/components/data-table";

export default function Overview() {
  const [items, setItems] = useState<Invoice[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [currency, setCurrency] = useState("DKK");

  useEffect(() => {
    api<Invoice[]>("/invoices").then(setItems).catch(() => {});
    api<Party[]>("/customers").then(setParties).catch(() => {});
    api<Organization[]>("/organizations")
      .then((orgs) => {
        if (orgs && orgs.length > 0 && orgs[0].currency) {
          setCurrency(orgs[0].currency);
        }
      })
      .catch(() => {});
  }, []);

  const outstanding = items
    .filter((i) => ["sent", "overdue", "partially_paid"].includes(i.status))
    .reduce((a, i) => a + Number(i.total), 0);
  const overdue = items
    .filter((i) => i.status === "overdue")
    .reduce((a, i) => a + Number(i.total), 0);
  const paid = items
    .filter((i) => i.status === "paid")
    .reduce((a, i) => a + Number(i.total), 0);
  const names = Object.fromEntries(parties.map((p) => [p.id, p.name]));

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="page-description">A clear view of your organization’s invoices.</p>
        </div>
        <Link className="button button-primary" href="/invoices/new">
          <Plus size={15} />
          New invoice
        </Link>
      </header>
      <section className="metrics">
        <Metric label="Outstanding" value={outstanding} currency={currency} note="Invoices awaiting payment" />
        <Metric label="Overdue" value={overdue} currency={currency} note="Past their due date" />
        <Metric label="Paid invoices" value={paid} currency={currency} note="Across all time" />
      </section>
      <div className="section-heading">
        <span>Recent invoices</span>
        <Link href="/invoices" className="text-link" style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}>
          View all <ArrowUpRight size={14} />
        </Link>
      </div>
      <InvoiceTable items={items.slice(0, 6)} partyNames={names} />
    </div>
  );
}

function Metric({
  label,
  value,
  currency,
  note,
}: {
  label: string;
  value: number;
  currency: string;
  note: string;
}) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {currency} {value.toLocaleString("en-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className="metric-note">{note}</div>
    </div>
  );
}
