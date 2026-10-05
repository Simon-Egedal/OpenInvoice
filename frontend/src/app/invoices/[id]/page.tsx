"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  ArrowLeft,
  CheckCircle,
  Download,
  Link2,
  Pencil,
  Send,
  Trash2,
  Unlink,
  X,
} from "lucide-react";
import {
  API,
  api,
  Invoice,
  InvoiceMatch,
  InvoicePayment,
  LinkableTransaction,
  Organization,
  Party,
  CurrentUser,
} from "@/lib/api";

import { InvoiceWorkflow } from "@/components/invoice-workflow";
import { minAmount, scaled, formatMoney } from "@/lib/money";

type Line = {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  tax_rate: string;
  line_total: string;
};

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [party, setParty] = useState<Party | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [payments, setPayments] = useState<InvoicePayment[]>([]);
  const [matches, setMatches] = useState<InvoiceMatch[]>([]);
  const [linkableTransactions, setLinkableTransactions] = useState<LinkableTransaction[]>([]);
  const [error, setError] = useState("");
  const [role, setRole] = useState("");
  const sendKey = useRef("");
  const sendBusy = useRef(false);

  // Modals state
  const [showPayModal, setShowPayModal] = useState(false);
  const [payMode, setPayMode] = useState<"full" | "custom">("full");
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("manual");
  const [payRef, setPayRef] = useState("");
  const [payNotes, setPayNotes] = useState("");

  const [showLinkModal, setShowLinkModal] = useState(false);
  const [selectedTxId, setSelectedTxId] = useState("");
  const [linkAmount, setLinkAmount] = useState("");

  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [inv, lns, pmts, mtchs, orgs, user] = await Promise.all([
        api<Invoice>(`/invoices/${id}`),
        api<Line[]>(`/invoices/${id}/lines`),
        api<InvoicePayment[]>(`/invoices/${id}/payments`),
        api<InvoiceMatch[]>(`/invoices/${id}/matches`),
        api<Organization[]>("/organizations"),
        api<CurrentUser>("/auth/me"),
      ]);
      setError("");
      setRole(user.role);
      setInvoice(inv);
      setLines(lns);
      setPayments(pmts);
      setMatches(mtchs);

      if (orgs && orgs.length > 0) {
        const found = inv.organization_id ? orgs.find((o) => o.id === inv.organization_id) : orgs[0];
        setOrg(found || orgs[0]);
      }

      if (inv.issued_at) {
        setParty(null);
      } else if (inv.customer_id) {
        api<Party>(`/customers/${inv.customer_id}`)
          .then(setParty)
          .catch(e => setError(e instanceof Error ? e.message : "Unable to load party details"));
      } else if (inv.supplier_id) {
        api<Party>(`/suppliers/${inv.supplier_id}`)
          .then(setParty)
          .catch(e => setError(e instanceof Error ? e.message : "Unable to load party details"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load invoice");
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function send() {
    if (sendBusy.current) return;
    sendBusy.current = true; setSubmitting(true); setError("");
    if (!sendKey.current) sendKey.current = crypto.randomUUID();
    try {
      await api(`/invoices/${id}/send`, { method: "POST", headers: {"Idempotency-Key": sendKey.current} });
      sendKey.current = "";
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Email failed");
    } finally { sendBusy.current = false; setSubmitting(false); }
  }

  function openPayModal() {
    if (!invoice) return;
    setPayMode("full");
    setPayAmount(scaled(String(invoice.due_amount)) > 0n ? invoice.due_amount : invoice.total);
    setPayMethod("manual");
    setPayRef("");
    setPayNotes("");
    setShowPayModal(true);
  }

  async function handleRecordPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!invoice) return;
    setSubmitting(true);
    setError("");
    try {
      const amount =
        payMode === "full" ? undefined : payAmount.replace(",", ".");
      await api(`/invoices/${id}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount: amount,
          payment_method: payMethod,
          reference: payRef || undefined,
          notes: payNotes || undefined,
        }),
      });
      setShowPayModal(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeletePayment(paymentId: string) {
    if (!confirm("Are you sure you want to delete this payment?")) return;
    setSubmitting(true);
    setError("");
    try {
      await api(`/invoices/${id}/payments/${paymentId}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete payment");
    } finally {
      setSubmitting(false);
    }
  }

  async function openLinkModal() {
    if (!invoice) return;
    setSelectedTxId("");
    setLinkAmount("");
    setShowLinkModal(true);
    try {
      const txs = await api<LinkableTransaction[]>(`/invoices/${id}/linkable-transactions`);
      setLinkableTransactions(txs.filter((t) => scaled(String(t.available_amount)) > 0n));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch linkable transactions");
    }
  }

  function handleSelectTx(tx: LinkableTransaction) {
    setSelectedTxId(tx.id);
    if (!invoice) return;
    setLinkAmount(minAmount(invoice.due_amount, tx.available_amount));
  }

  async function handleLinkTransaction(e: React.FormEvent) {
    e.preventDefault();
    if (!invoice || !selectedTxId) return;
    setSubmitting(true);
    setError("");
    try {
      const parsedAmount = linkAmount ? linkAmount.replace(",", ".") : undefined;
      await api(`/invoices/${id}/link-transaction`, {
        method: "POST",
        body: JSON.stringify({
          transaction_id: selectedTxId,
          amount: parsedAmount,
        }),
      });
      setShowLinkModal(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to link transaction");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUnlinkMatch(matchId: string) {
    if (!confirm("Are you sure you want to unlink this bank transaction?")) return;
    setSubmitting(true);
    setError("");
    try {
      await api(`/invoices/${id}/matches/${matchId}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlink transaction");
    } finally {
      setSubmitting(false);
    }
  }

  if (!invoice) {
    return (
      <div className="page">
        <p>{error || "Loading invoice…"}</p>
      </div>
    );
  }

  const canWrite = ["owner", "admin", "accountant", "member"].includes(role);
  const isFullyPaid = scaled(String(invoice.due_amount)) <= 0n;
  const canPay = canWrite && !isFullyPaid && ["issued", "sent", "approved", "partially_paid", "overdue"].includes(invoice.status);
  const orgDisplayName = invoice.organization_name || org?.name || "Organization";
  const orgLogoUrl = invoice.organization_logo_url
    ? `${API}/api/v1${invoice.organization_logo_url}`
    : !invoice.issued_at && org?.logo_key
    ? `${API}/api/v1/organizations/${org.id}/logo`
    : null;

  const activeRecipient = party || invoice.recipient || (invoice.recipient_name ? {
    id: invoice.customer_id || invoice.supplier_id || "",
    name: invoice.recipient_name,
    email: invoice.recipient_email || null,
    phone: invoice.recipient_phone || null,
    address: invoice.recipient_address || null,
    postal_code: invoice.recipient_postal_code || null,
    city: invoice.recipient_city || null,
    country: invoice.recipient_country || "DK",
    vat_number: invoice.recipient_vat_number || null,
    payment_information: null,
    notes: null,
  } : null);

  return (
    <div className="page">
      <Link
        href="/invoices"
        className="text-link"
        style={{
          fontSize: 12,
          display: "inline-flex",
          gap: 5,
          alignItems: "center",
          marginBottom: 17,
        }}
      >
        <ArrowLeft size={14} />
        Invoices
      </Link>

      <header className="page-head">
        <div>
          <h1 className="page-title">{invoice.invoice_number}</h1>
          <p className="page-description">
            {invoice.invoice_type === "outgoing" ? "Outgoing invoice" : "Incoming invoice"} ·{" "}
            <span className={`status ${invoice.status}`}>
              {invoice.status.replaceAll("_", " ")}
            </span>
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {canWrite && invoice.status === "draft" && invoice.invoice_type === "outgoing" && (
            <Link className="button" href={`/invoices/${id}/edit`}>
              <Pencil size={14} />
              Edit draft
            </Link>
          )}
          <a
            className="button"
            href={`${API}/api/v1/invoices/${id}/pdf`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Download size={14} />
            PDF
          </a>
          {canWrite && invoice.invoice_type === "outgoing" && !["cancelled", "rejected"].includes(invoice.status) && (
            <button className="button" onClick={send} disabled={submitting || !canWrite}>
              <Send size={14} />
              Send invoice
            </button>
          )}
          {canPay && (
            <>
              <button className="button" onClick={openLinkModal} disabled={submitting || !canWrite}>
                <Link2 size={14} />
                Link transaction
              </button>
              <button
                className="button button-primary"
                onClick={openPayModal}
                disabled={submitting || !canWrite}
              >
                <CheckCircle size={14} />
                Mark as paid
              </button>
            </>
          )}
        </div>
      </header>
      <InvoiceWorkflow invoice={invoice} onChange={loadData}/>

      {/* Organization and Recipient Branding Card */}
      <div
        className="invoice-org-card"
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          padding: "20px 24px",
          background: "#fff",
          border: "1px solid var(--line)",
          borderRadius: "var(--radius)",
          marginBottom: 20,
          gap: 20,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          {orgLogoUrl ? (
            <img
              src={orgLogoUrl}
              alt={orgDisplayName}
              style={{
                width: 48,
                height: 48,
                objectFit: "contain",
                borderRadius: 4,
                background: "#fff",
                border: "1px solid var(--line)",
                padding: 3,
              }}
            />
          ) : (
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 4,
                background: "var(--accent-wash)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                fontWeight: 700,
                fontSize: 18,
                border: "1px solid var(--line)",
                flexShrink: 0,
              }}
            >
              {(orgDisplayName[0] || "O").toUpperCase()}
            </div>
          )}
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.2px" }}>
              {orgDisplayName}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
              {invoice.invoice_type === "outgoing" ? "Issuer" : "Recipient organization"}
              {org?.country ? ` · ${org.country}` : ""}
            </div>
          </div>
        </div>

        {activeRecipient && (
          <div style={{ textAlign: "right", maxWidth: 320 }}>
            <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: 4 }}>
              {invoice.invoice_type === "outgoing" ? "Billed to (Recipient)" : "Supplier"}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>
              {activeRecipient.name}
            </div>
            {activeRecipient.address && (
              <div style={{ fontSize: 12, color: "#424a45", marginTop: 2 }}>
                {activeRecipient.address}
              </div>
            )}
            {(activeRecipient.postal_code || activeRecipient.city || activeRecipient.country) && (
              <div style={{ fontSize: 12, color: "#424a45" }}>
                {[activeRecipient.postal_code, activeRecipient.city].filter(Boolean).join(" ")}
                {activeRecipient.country ? `, ${activeRecipient.country}` : ""}
              </div>
            )}
            {activeRecipient.vat_number && (
              <div className="mono" style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
                VAT: {activeRecipient.vat_number}
              </div>
            )}
            {activeRecipient.email && (
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                {activeRecipient.email}
              </div>
            )}
            {activeRecipient.phone && (
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>
                {activeRecipient.phone}
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <p className="error-text" role="alert" style={{ marginBottom: 16 }}>
          {error}
        </p>
      )}

      {/* Metrics breakdown: Total, Paid, Due */}
      <div className="metrics">
        <div className="metric">
          <div className="metric-label">Total amount</div>
          <div className="metric-value">
            {invoice.currency} {formatMoney(String(invoice.total))}
          </div>
          <div className="metric-note">Subtotal + VAT</div>
        </div>
        <div className="metric">
          <div className="metric-label">Paid to date</div>
          <div className="metric-value" style={{ color: scaled(String(invoice.paid_amount)) > 0n ? "#3d7150" : undefined }}>
            {invoice.currency} {formatMoney(String(invoice.paid_amount || 0))}
          </div>
          <div className="metric-note">
            {matches.length + payments.length} payment record{matches.length + payments.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="metric">
          <div className="metric-label">Due balance</div>
          <div
            className="metric-value"
            style={{
              color: isFullyPaid ? "#3d7150" : scaled(String(invoice.paid_amount)) > 0n ? "#a05e24" : undefined,
            }}
          >
            {invoice.currency} {formatMoney(String(invoice.due_amount || 0))}
          </div>
          <div className="metric-note">
            {isFullyPaid ? "Fully settled" : "Remaining to pay"}
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <div className="detail-label">Organization</div>
          <div className="detail-value" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {orgLogoUrl ? (
              <img
                src={orgLogoUrl}
                alt=""
                style={{ width: 16, height: 16, objectFit: "contain", borderRadius: 2 }}
              />
            ) : (
              <span
                style={{
                  display: "inline-block",
                  width: 14,
                  height: 14,
                  borderRadius: 2,
                  background: "var(--accent-wash)",
                  color: "var(--accent)",
                  fontSize: 9,
                  fontWeight: 700,
                  textAlign: "center",
                  lineHeight: "14px",
                }}
              >
                {(orgDisplayName[0] || "O").toUpperCase()}
              </span>
            )}
            <span>{orgDisplayName}</span>
          </div>
        </div>
        <div>
          <div className="detail-label">
            {invoice.invoice_type === "outgoing" ? "Recipient" : "Supplier"}
          </div>
          <div className="detail-value">
            {activeRecipient ? (
              <div>
                <div style={{ fontWeight: 600 }}>{activeRecipient.name}</div>
                {(activeRecipient.address || activeRecipient.city || activeRecipient.country) && (
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                    {[activeRecipient.address, activeRecipient.postal_code, activeRecipient.city, activeRecipient.country].filter(Boolean).join(", ")}
                  </div>
                )}
                {activeRecipient.vat_number && (
                  <div className="mono" style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>
                    VAT: {activeRecipient.vat_number}
                  </div>
                )}
              </div>
            ) : (
              "—"
            )}
          </div>
        </div>
        <div>
          <div className="detail-label">Issue date</div>
          <div className="detail-value">{invoice.issue_date}</div>
        </div>
        <div>
          <div className="detail-label">Due date</div>
          <div className="detail-value">{invoice.due_date}</div>
        </div>
        <div>
          <div className="detail-label">Invoice number</div>
          <div className="detail-value">{invoice.invoice_number}</div>
        </div>
        <div>
          <div className="detail-label">Payment status</div>
          <div className="detail-value">
            <span className={`status ${invoice.status}`}>
              {invoice.status.replaceAll("_", " ")}
            </span>
          </div>
        </div>
      </div>

      {/* Line items table */}
      <div className="section-heading" style={{ marginTop: 28 }}>
        Line items
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th>Quantity</th>
              <th>Unit price</th>
              <th>VAT</th>
              <th style={{ textAlign: "right" }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.id}>
                <td className="td-strong">{line.description}</td>
                <td className="mono">{line.quantity}</td>
                <td className="mono">{formatMoney(String(line.unit_price))}</td>
                <td className="mono">{line.tax_rate}%</td>
                <td className="mono" style={{ textAlign: "right" }}>
                  {formatMoney(String(line.line_total))}
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
            {invoice.currency} {formatMoney(String(invoice.subtotal))}
          </span>
        </div>
        <div className="invoice-total-row">
          <span>VAT</span>
          <span className="mono">
            {invoice.currency} {formatMoney(String(invoice.tax_amount))}
          </span>
        </div>
        <div className="invoice-total-row final">
          <span>Total</span>
          <span className="mono">
            {invoice.currency} {formatMoney(String(invoice.total))}
          </span>
        </div>
        {scaled(String(invoice.paid_amount)) > 0n && (
          <>
            <div className="invoice-total-row" style={{ color: "#3d7150" }}>
              <span>Total paid</span>
              <span className="mono">
                - {invoice.currency} {formatMoney(String(invoice.paid_amount))}
              </span>
            </div>
            <div className="invoice-total-row final" style={{ borderTop: "1px solid var(--line)" }}>
              <span>Amount due</span>
              <span
                className="mono"
                style={{ color: isFullyPaid ? "#3d7150" : "#a05e24" }}
              >
                {invoice.currency} {formatMoney(String(invoice.due_amount))}
              </span>
            </div>
          </>
        )}
      </div>

      {invoice.notes && (
        <div className="notice" style={{ marginTop: 30 }}>
          {invoice.notes}
        </div>
      )}

      {/* Payments & Bank Transaction Matches Section */}
      <div style={{ marginTop: 40 }}>
        <div className="section-heading">
          <span>Payments & Linked Transactions</span>
          <div style={{ display: "flex", gap: 8 }}>
            {canPay && (
              <>
                <button
                  className="button"
                  onClick={openLinkModal}
                  style={{ fontSize: 11, padding: "5px 9px" }}
                  disabled={submitting || !canWrite}
                >
                  <Link2 size={12} />
                  Link transaction
                </button>
                <button
                  className="button button-primary"
                  onClick={openPayModal}
                  style={{ fontSize: 11, padding: "5px 9px" }}
                  disabled={submitting || !canWrite}
                >
                  <CheckCircle size={12} />
                  Record payment
                </button>
              </>
            )}
          </div>
        </div>

        {matches.length === 0 && payments.length === 0 ? (
          <div className="notice" style={{ marginTop: 8 }}>
            No payments or bank transaction links have been recorded yet. Use &ldquo;Mark as
            paid&rdquo; or &ldquo;Link transaction&rdquo; above to settle this invoice.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 20 }}>
            {/* Linked Bank Transactions */}
            {matches.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 8 }}>
                  Linked Bank Transactions
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Counterparty</th>
                        <th>Reference</th>
                        <th style={{ textAlign: "right" }}>Linked amount</th>
                        <th style={{ textAlign: "right" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {matches.map((m) => (
                        <tr key={m.id}>
                          <td>
                            {m.transaction_booked_at
                              ? new Date(m.transaction_booked_at).toLocaleDateString()
                              : "—"}
                          </td>
                          <td className="td-strong">{m.transaction_description ?? "Bank transaction"}</td>
                          <td>{m.transaction_counterparty || "—"}</td>
                          <td className="mono">{m.transaction_reference ?? "—"}</td>
                          <td className="mono" style={{ textAlign: "right", color: "#3d7150", fontWeight: 600 }}>
                            {invoice.currency} {formatMoney(String(m.amount))}
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="button"
                              style={{ padding: "4px 8px", fontSize: 11, color: "#a34d43" }}
                              onClick={() => handleUnlinkMatch(m.id)}
                              disabled={submitting || !canWrite}
                              title="Unlink transaction"
                            >
                              <Unlink size={12} />
                              Unlink
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Manual Payments */}
            {payments.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 8 }}>
                  Manual Payments
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Method</th>
                        <th>Reference</th>
                        <th>Notes</th>
                        <th style={{ textAlign: "right" }}>Amount</th>
                        <th style={{ textAlign: "right" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payments.map((p) => (
                        <tr key={p.id}>
                          <td>{p.payment_date}</td>
                          <td className="td-strong" style={{ textTransform: "capitalize" }}>
                            {p.payment_method.replaceAll("_", " ")}
                          </td>
                          <td className="mono">{p.reference ?? "—"}</td>
                          <td>{p.notes ?? "—"}</td>
                          <td className="mono" style={{ textAlign: "right", color: "#3d7150", fontWeight: 600 }}>
                            {invoice.currency} {formatMoney(String(p.amount))}
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="button"
                              style={{ padding: "4px 8px", fontSize: 11, color: "#a34d43" }}
                              onClick={() => handleDeletePayment(p.id)}
                              disabled={submitting || !canWrite}
                              title="Delete payment"
                            >
                              <Trash2 size={12} />
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Mark as Paid Modal */}
      {showPayModal && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-head">
              <h2>Record Payment</h2>
              <button
                className="icon-button"
                onClick={() => setShowPayModal(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleRecordPayment}>
              <div style={{ display: "grid", gap: 14 }}>
                <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
                  <button
                    type="button"
                    className={`button ${payMode === "full" ? "button-primary" : ""}`}
                    style={{ flex: 1, justifyContent: "center" }}
                    onClick={() => {
                      setPayMode("full");
                      setPayAmount(invoice.due_amount);
                    }}
                  >
                    Full Due ({invoice.currency} {formatMoney(String(invoice.due_amount))})
                  </button>
                  <button
                    type="button"
                    className={`button ${payMode === "custom" ? "button-primary" : ""}`}
                    style={{ flex: 1, justifyContent: "center" }}
                    onClick={() => setPayMode("custom")}
                  >
                    Custom amount
                  </button>
                </div>

                {payMode === "custom" && (
                  <div className="field">
                    <label htmlFor="pay-amount">Amount ({invoice.currency})</label>
                    <input
                      id="pay-amount"
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      value={payAmount}
                      onChange={(e) => setPayAmount(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                )}

                <div className="field">
                  <label htmlFor="pay-method">Payment method</label>
                  <select
                    id="pay-method"
                    value={payMethod}
                    onChange={(e) => setPayMethod(e.target.value)}
                  >
                    <option value="manual">Manual / Cash</option>
                    <option value="bank_transfer">Bank transfer</option>
                    <option value="credit_card">Credit card</option>
                    <option value="mobilepay">MobilePay</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="pay-ref">Reference (optional)</label>
                  <input
                    id="pay-ref"
                    type="text"
                    value={payRef}
                    onChange={(e) => setPayRef(e.target.value)}
                    placeholder="e.g. Wire transfer ID, check #"
                  />
                </div>

                <div className="field">
                  <label htmlFor="pay-notes">Notes (optional)</label>
                  <textarea
                    id="pay-notes"
                    value={payNotes}
                    onChange={(e) => setPayNotes(e.target.value)}
                    placeholder="Internal memo or payment notes"
                    rows={2}
                  />
                </div>
              </div>

              <div className="row-actions" style={{ marginTop: 22 }}>
                <button
                  type="button"
                  className="button"
                  onClick={() => setShowPayModal(false)}
                  disabled={submitting || !canWrite}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  disabled={submitting || !canWrite}
                >
                  {submitting ? "Saving…" : "Save payment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Link Bank Transaction Modal */}
      {showLinkModal && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 640 }}>
            <div className="modal-head">
              <div>
                <h2>Link Bank Transaction</h2>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 12 }}>
                  Select an available transaction. Smaller transactions will deduct from the invoice due amount.
                </p>
              </div>
              <button
                className="icon-button"
                onClick={() => setShowLinkModal(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {linkableTransactions.length === 0 ? (
              <div style={{ padding: "20px 0" }}>
                <div className="notice">
                  No bank transactions with available unallocated funds found. Connect a bank account in{" "}
                  <Link href="/banking" className="text-link">
                    Banking
                  </Link>{" "}
                  to import bank statements, or record a manual payment above.
                </div>
              </div>
            ) : (
              <form onSubmit={handleLinkTransaction}>
                <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 6, marginBottom: 16 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Select</th>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Counterparty</th>
                        <th style={{ textAlign: "right" }}>Available</th>
                      </tr>
                    </thead>
                    <tbody>
                      {linkableTransactions.map((tx) => {
                        const isSelected = selectedTxId === tx.id;
                        return (
                          <tr
                            key={tx.id}
                            style={{
                              background: isSelected ? "var(--accent-wash)" : undefined,
                              cursor: "pointer",
                            }}
                            onClick={() => handleSelectTx(tx)}
                          >
                            <td>
                              <input
                                type="radio"
                                name="tx"
                                checked={isSelected}
                                onChange={() => handleSelectTx(tx)}
                                aria-label={`Select transaction ${tx.description}`}
                              />
                            </td>
                            <td>{new Date(tx.booked_at).toLocaleDateString()}</td>
                            <td className="td-strong">{tx.description}</td>
                            <td>{tx.counterparty || "—"}</td>
                            <td className="mono" style={{ textAlign: "right", color: "#3d7150", fontWeight: 600 }}>
                              {tx.currency} {formatMoney(String(tx.available_amount))}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {selectedTxId && (
                  <div className="field" style={{ marginBottom: 14 }}>
                    <label htmlFor="link-amount">
                      Allocated amount to link ({invoice.currency})
                    </label>
                    <input
                      id="link-amount"
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      value={linkAmount}
                      onChange={(e) => setLinkAmount(e.target.value)}
                    />
                    <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                      Defaults to the lesser of the transaction balance and remaining invoice due amount.
                    </div>
                  </div>
                )}

                <div className="row-actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => setShowLinkModal(false)}
                    disabled={submitting || !canWrite}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="button button-primary"
                    disabled={!selectedTxId || submitting}
                  >
                    {submitting ? "Linking…" : "Link transaction"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
