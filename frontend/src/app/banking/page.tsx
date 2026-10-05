"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  RefreshCw,
  WalletCards,
  X,
  Building2,
  Check,
  Link2,
  Unlink,
} from "lucide-react";
import { api, BankTransactionItem, Invoice } from "@/lib/api";

type Account = {
  id: string;
  name: string;
  bank: string;
  masked_number: string;
  currency: string;
  balance: string;
  last_synced_at: string | null;
};

type ASPSP = {
  name: string;
  country: string;
  logo?: string | null;
  psu_types?: string[];
};

type ASPSPResponse = {
  country: string;
  banks: ASPSP[];
};

export default function Banking() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTx] = useState<BankTransactionItem[]>([]);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [showBankPicker, setShowBankPicker] = useState(false);
  const [availableBanks, setAvailableBanks] = useState<ASPSP[]>([]);
  const [selectedBank, setSelectedBank] = useState<ASPSP | null>(null);

  // Match modal state
  const [showMatchModal, setShowMatchModal] = useState(false);
  const [matchTx, setMatchTx] = useState<BankTransactionItem | null>(null);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState("");
  const [matchAmount, setMatchAmount] = useState("");
  const [matching, setMatching] = useState(false);

  const loadData = async () => {
    try {
      const [accs, txs] = await Promise.all([
        api<Account[]>("/banking/accounts"),
        api<BankTransactionItem[]>("/banking/transactions"),
      ]);
      setAccounts(Array.isArray(accs) ? accs : []);
      setTx(Array.isArray(txs) ? txs : []);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load banking data");
      setAccounts([]);
      setTx([]);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  async function handleConnectClick() {
    setConnecting(true);
    setError("");
    try {
      const res = await api<ASPSPResponse>("/banking/aspsps");
      if (res.banks && res.banks.length > 0) {
        setAvailableBanks(res.banks);
        const preferred =
          res.banks.find((b) => b.name.toLowerCase().includes("mock")) || res.banks[0];
        setSelectedBank(preferred);
        setShowBankPicker(true);
      } else {
        await initiateAuthorization(null);
      }
    } catch {
      await initiateAuthorization(null);
    } finally {
      setConnecting(false);
    }
  }

  async function initiateAuthorization(bank: ASPSP | null) {
    setConnecting(true);
    setError("");
    try {
      const payload = bank
        ? { aspsp_name: bank.name, aspsp_country: bank.country }
        : {};
      const r = await api<{ authorization_url: string }>("/banking/connections/authorize", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      window.location.href = r.authorization_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to initiate bank connection");
      setShowBankPicker(false);
      setConnecting(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await api("/banking/sync", { method: "POST" });
      await loadData();
    } catch {
      await loadData();
    } finally {
      setRefreshing(false);
    }
  }

  async function openLinkInvoiceModal(tx: BankTransactionItem) {
    setMatchTx(tx);
    setSelectedInvoiceId("");
    setMatchAmount("");
    setShowMatchModal(true);
    try {
      const allInvoices = await api<Invoice[]>("/invoices");
      const unpaid = allInvoices.filter((inv) => Number(inv.due_amount ?? inv.total) > 0);
      setOpenInvoices(unpaid);
      if (unpaid.length > 0) {
        const first = unpaid[0];
        setSelectedInvoiceId(first.id);
        const unallocated = Number(tx.unmatched_amount || Math.abs(Number(tx.amount)));
        const due = Number(first.due_amount ?? first.total);
        setMatchAmount(Math.min(unallocated, due).toFixed(2));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load invoices");
    }
  }

  function handleSelectInvoice(invoiceId: string) {
    setSelectedInvoiceId(invoiceId);
    if (!matchTx) return;
    const inv = openInvoices.find((i) => i.id === invoiceId);
    if (!inv) return;
    const unallocated = Number(matchTx.unmatched_amount || Math.abs(Number(matchTx.amount)));
    const due = Number(inv.due_amount ?? inv.total);
    setMatchAmount(Math.min(unallocated, due).toFixed(2));
  }

  async function handleLinkSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!matchTx || !selectedInvoiceId) return;
    setMatching(true);
    setError("");
    try {
      const amount = matchAmount ? parseFloat(matchAmount.replace(",", ".")) : undefined;
      await api(`/banking/transactions/${matchTx.id}/link-invoice`, {
        method: "POST",
        body: JSON.stringify({
          invoice_id: selectedInvoiceId,
          amount: amount,
        }),
      });
      setShowMatchModal(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to link invoice");
    } finally {
      setMatching(false);
    }
  }

  async function handleUnlinkMatch(matchId: string) {
    if (!confirm("Are you sure you want to unlink this invoice from the transaction?")) return;
    try {
      await api(`/banking/matches/${matchId}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlink match");
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Banking</h1>
          <p className="page-description">Accounts and transactions for your organization.</p>
        </div>
        <button
          className="button button-primary"
          onClick={handleConnectClick}
          disabled={connecting}
        >
          <WalletCards size={15} />
          {connecting ? "Connecting…" : "Connect bank account"}
        </button>
      </header>

      {/* Bank Selection Modal */}
      {showBankPicker && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 16,
          }}
        >
          <div
            style={{
              background: "var(--background)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              maxWidth: 480,
              width: "100%",
              padding: "24px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 600 }}>Select your bank</h2>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.875rem" }}>
                  Choose a supported financial institution to authorize access.
                </p>
              </div>
              <button
                className="button button-subtle"
                style={{ padding: 6 }}
                onClick={() => setShowBankPicker(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div
              style={{
                maxHeight: "280px",
                overflowY: "auto",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                marginBottom: 20,
              }}
            >
              {(availableBanks || []).map((bank) => {
                const isSelected = selectedBank?.name === bank.name;
                return (
                  <button
                    key={bank.name}
                    type="button"
                    onClick={() => setSelectedBank(bank)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "12px 14px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: isSelected ? "var(--surface-hover)" : "var(--surface)",
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Building2 size={18} style={{ color: "var(--muted)" }} />
                      <div>
                        <div style={{ fontWeight: isSelected ? 600 : 500, fontSize: "0.95rem" }}>
                          {bank.name}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                          {bank.country} • {(bank.psu_types || []).join(", ") || "all accounts"}
                        </div>
                      </div>
                    </div>
                    {isSelected && <Check size={18} style={{ color: "var(--accent)" }} />}
                  </button>
                );
              })}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                className="button button-subtle"
                onClick={() => setShowBankPicker(false)}
                disabled={connecting}
              >
                Cancel
              </button>
              <button
                className="button button-primary"
                onClick={() => initiateAuthorization(selectedBank)}
                disabled={!selectedBank || connecting}
              >
                {connecting ? "Connecting…" : "Continue to bank"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Match to Invoice Modal */}
      {showMatchModal && matchTx && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 560 }}>
            <div className="modal-head">
              <div>
                <h2>Link Transaction to Invoice</h2>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 12 }}>
                  {matchTx.description} · {matchTx.currency}{" "}
                  {Number(matchTx.amount).toLocaleString("en-DK", { minimumFractionDigits: 2 })}
                  {Number(matchTx.unmatched_amount || 0) < Math.abs(Number(matchTx.amount)) && (
                    <span>
                      {" "}
                      (Available to link: {matchTx.currency}{" "}
                      {Number(matchTx.unmatched_amount).toFixed(2)})
                    </span>
                  )}
                </p>
              </div>
              <button
                className="icon-button"
                onClick={() => setShowMatchModal(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {openInvoices.length === 0 ? (
              <div style={{ padding: "20px 0" }}>
                <div className="notice">
                  No unpaid or partially paid invoices found. Create an invoice first or all
                  invoices are already settled.
                </div>
              </div>
            ) : (
              <form onSubmit={handleLinkSubmit}>
                <div className="field" style={{ marginBottom: 14 }}>
                  <label htmlFor="select-invoice">Choose Invoice to Match</label>
                  <select
                    id="select-invoice"
                    value={selectedInvoiceId}
                    onChange={(e) => handleSelectInvoice(e.target.value)}
                    required
                  >
                    {openInvoices.map((inv) => (
                      <option key={inv.id} value={inv.id}>
                        {inv.invoice_number} ({inv.invoice_type}) — Total: {inv.currency}{" "}
                        {Number(inv.total).toFixed(2)} | Due: {inv.currency}{" "}
                        {Number(inv.due_amount ?? inv.total).toFixed(2)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field" style={{ marginBottom: 16 }}>
                  <label htmlFor="match-amount">Amount to link ({matchTx.currency})</label>
                  <input
                    id="match-amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={matchAmount}
                    onChange={(e) => setMatchAmount(e.target.value)}
                  />
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                    If less than full invoice amount, this will deduct from the invoice due balance.
                  </div>
                </div>

                <div className="row-actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => setShowMatchModal(false)}
                    disabled={matching}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="button button-primary"
                    disabled={!selectedInvoiceId || matching}
                  >
                    {matching ? "Linking…" : "Link invoice"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      <div className="section-heading">Accounts</div>
      {!Array.isArray(accounts) || accounts.length === 0 ? (
        <div className="notice">
          No accounts connected. Connect a bank account when a banking provider is configured.
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Bank</th>
                <th>Account number</th>
                <th>Last synced</th>
                <th style={{ textAlign: "right" }}>Balance</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td className="td-strong">{a.name}</td>
                  <td>{a.bank}</td>
                  <td className="mono">{a.masked_number}</td>
                  <td>
                    {a.last_synced_at
                      ? new Date(a.last_synced_at).toLocaleString()
                      : "Recently connected"}
                  </td>
                  <td className="mono" style={{ textAlign: "right" }}>
                    {a.currency}{" "}
                    {Number(a.balance).toLocaleString("en-DK", {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="section-heading" style={{ marginTop: 34 }}>
        Recent transactions{" "}
        <button className="button" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Syncing…" : "Refresh"}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Counterparty</th>
              <th>Reference</th>
              <th style={{ textAlign: "right" }}>Amount</th>
              <th>Reconciliation / Match</th>
              <th style={{ textAlign: "right" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {!Array.isArray(transactions) || transactions.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", color: "var(--muted)", padding: "24px" }}>
                  No transactions yet. Connect a bank account to see transactions.
                </td>
              </tr>
            ) : (
              transactions.map((t) => {
                const hasMatches = Array.isArray(t.matches) && t.matches.length > 0;
                const isFullyMatched = hasMatches && Number(t.unmatched_amount || 0) <= 0;
                const isPartiallyMatched = hasMatches && !isFullyMatched;

                return (
                  <tr key={t.id}>
                    <td>{new Date(t.booked_at).toLocaleDateString()}</td>
                    <td className="td-strong">{t.description}</td>
                    <td>{t.counterparty || "—"}</td>
                    <td className="mono">{t.reference ?? "—"}</td>
                    <td
                      className="mono"
                      style={{
                        textAlign: "right",
                        color: Number(t.amount) > 0 ? "#3d7150" : undefined,
                      }}
                    >
                      {t.currency}{" "}
                      {Number(t.amount).toLocaleString("en-DK", {
                        minimumFractionDigits: 2,
                      })}
                    </td>
                    <td>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div>
                          {isFullyMatched && <span className="status paid">Matched</span>}
                          {isPartiallyMatched && (
                            <span className="status partially_paid">Partially matched</span>
                          )}
                          {!hasMatches && <span className="status">Unmatched</span>}
                        </div>
                        {hasMatches && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                            {t.matches!.map((m) => (
                              <span
                                key={m.match_id}
                                style={{
                                  fontSize: 11,
                                  background: "#f0f2f0",
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                }}
                              >
                                <Link
                                  href={`/invoices/${m.invoice_id}`}
                                  className="text-link"
                                  style={{ fontWeight: 600 }}
                                >
                                  {m.invoice_number}
                                </Link>
                                <span className="mono">
                                  ({t.currency} {Number(m.amount).toFixed(2)})
                                </span>
                                <button
                                  type="button"
                                  style={{
                                    border: 0,
                                    background: "transparent",
                                    cursor: "pointer",
                                    padding: 0,
                                    color: "#a34d43",
                                    display: "inline-flex",
                                    alignItems: "center",
                                  }}
                                  title="Unlink"
                                  onClick={() => handleUnlinkMatch(m.match_id)}
                                >
                                  <Unlink size={10} />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      {!isFullyMatched && (
                        <button
                          className="button"
                          style={{ padding: "4px 8px", fontSize: 11 }}
                          onClick={() => openLinkInvoiceModal(t)}
                          title="Link to an invoice"
                        >
                          <Link2 size={12} />
                          Link invoice
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {error && (
        <p className="error-text" role="alert" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}
    </div>
  );
}
