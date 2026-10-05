"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { api, Organization, Party } from "@/lib/api";

type Line = {
  description: string;
  quantity: string;
  unit_price: string;
  tax_rate: string;
};

export default function NewInvoice() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Party[]>([]);
  const [currency, setCurrency] = useState("DKK");
  const [lines, setLines] = useState<Line[]>([
    { description: "", quantity: "1", unit_price: "0.00", tax_rate: "25" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    api<Party[]>("/customers").then(setCustomers).catch(() => {});
    api<Organization[]>("/organizations")
      .then((orgs) => {
        if (orgs && orgs.length > 0 && orgs[0].currency) {
          setCurrency(orgs[0].currency);
        }
      })
      .catch(() => {});
  }, []);

  const subtotal = lines.reduce(
    (n, l) => n + (Number(l.quantity) || 0) * (Number(l.unit_price) || 0),
    0
  );
  const tax = lines.reduce(
    (n, l) =>
      n +
      ((Number(l.quantity) || 0) *
        (Number(l.unit_price) || 0) *
        (Number(l.tax_rate) || 0)) /
        100,
    0
  );

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(e.currentTarget as HTMLFormElement);
    try {
      const result = await api<{ id: string }>("/invoices", {
        method: "POST",
        body: JSON.stringify({
          invoice_number: form.get("invoice_number"),
          invoice_type: "outgoing",
          customer_id: form.get("customer_id"),
          issue_date: form.get("issue_date"),
          due_date: form.get("due_date"),
          currency: form.get("currency") || currency,
          notes: form.get("notes") || null,
          lines: lines.map((l) => ({
            ...l,
            quantity: Number(l.quantity),
            unit_price: Number(l.unit_price),
            tax_rate: Number(l.tax_rate),
          })),
        }),
      });
      router.push(`/invoices/${result.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create invoice");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <Link
        href="/invoices"
        className="text-link"
        style={{
          fontSize: 12,
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          marginBottom: 16,
        }}
      >
        <ArrowLeft size={14} />
        Invoices
      </Link>
      <header className="page-head">
        <div>
          <h1 className="page-title">New invoice</h1>
          <p className="page-description">Create an outgoing invoice for a customer.</p>
        </div>
      </header>
      <form onSubmit={save}>
        <div className="section-heading">Invoice details</div>
        <div className="form-grid" style={{ maxWidth: 800, marginBottom: 28 }}>
          <Field label="Customer">
            <select required name="customer_id" defaultValue="">
              <option value="" disabled>
                Select a customer
              </option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Invoice number">
            <input
              name="invoice_number"
              required
              defaultValue={`INV-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`}
            />
          </Field>
          <Field label="Issue date">
            <input name="issue_date" type="date" required defaultValue={today} />
          </Field>
          <Field label="Due date">
            <input
              name="due_date"
              type="date"
              required
              defaultValue={new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10)}
            />
          </Field>
          <Field label="Currency">
            <input
              name="currency"
              required
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              maxLength={10}
            />
          </Field>
        </div>
        <div className="section-heading" style={{ marginBottom: 10 }}>
          Invoice lines{" "}
          <button
            type="button"
            className="button"
            onClick={() =>
              setLines([
                ...lines,
                { description: "", quantity: "1", unit_price: "0.00", tax_rate: "25" },
              ])
            }
          >
            <Plus size={14} />
            Add line
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Description</th>
                <th>Quantity</th>
                <th>Unit price</th>
                <th>VAT %</th>
                <th style={{ textAlign: "right" }}>Line total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i}>
                  <td>
                    <input
                      required
                      className="filter"
                      style={{ width: "100%", minWidth: 140 }}
                      aria-label="Description"
                      value={l.description}
                      onChange={(e) => update(i, "description", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      required
                      type="number"
                      min="0.001"
                      step="0.001"
                      className="filter"
                      style={{ width: 78 }}
                      aria-label="Quantity"
                      value={l.quantity}
                      onChange={(e) => update(i, "quantity", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      required
                      type="number"
                      min="0"
                      step="0.01"
                      className="filter"
                      style={{ width: 100 }}
                      aria-label="Unit price"
                      value={l.unit_price}
                      onChange={(e) => update(i, "unit_price", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      required
                      type="number"
                      min="0"
                      max="100"
                      step="0.01"
                      className="filter"
                      style={{ width: 74 }}
                      aria-label="VAT rate"
                      value={l.tax_rate}
                      onChange={(e) => update(i, "tax_rate", e.target.value)}
                    />
                  </td>
                  <td className="mono" style={{ textAlign: "right" }}>
                    {((Number(l.quantity) || 0) * (Number(l.unit_price) || 0)).toFixed(2)}
                  </td>
                  <td>
                    <button
                      type="button"
                      aria-label="Remove line"
                      className="icon-button"
                      onClick={() => setLines(lines.filter((_, j) => j !== i))}
                      disabled={lines.length === 1}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="invoice-totals">
          <div className="invoice-total-row">
            <span>Subtotal</span>
            <span className="mono">
              {currency} {subtotal.toFixed(2)}
            </span>
          </div>
          <div className="invoice-total-row">
            <span>VAT</span>
            <span className="mono">
              {currency} {tax.toFixed(2)}
            </span>
          </div>
          <div className="invoice-total-row final">
            <span>Total</span>
            <span className="mono">
              {currency} {(subtotal + tax).toFixed(2)}
            </span>
          </div>
        </div>
        <div className="field" style={{ maxWidth: 800, marginTop: 23 }}>
          <label htmlFor="notes">Notes</label>
          <textarea
            id="notes"
            name="notes"
            placeholder="Payment terms or a note for your customer"
          />
        </div>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <div className="row-actions">
          <Link className="button" href="/invoices">
            Cancel
          </Link>
          <button className="button button-primary" disabled={saving}>
            {saving ? "Saving…" : "Save draft"}
          </button>
        </div>
      </form>
    </div>
  );

  function update(index: number, key: keyof Line, value: string) {
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, [key]: value } : line))
    );
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}
