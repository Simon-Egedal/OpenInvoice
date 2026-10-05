"use client";

import { useEffect, useState } from "react";
import { RefreshCw, WalletCards, X, Building2, Check } from "lucide-react";
import { api } from "@/lib/api";

type Account = {
  id: string;
  name: string;
  bank: string;
  masked_number: string;
  currency: string;
  balance: string;
  last_synced_at: string | null;
};

type Tx = {
  id: string;
  booked_at: string;
  description: string;
  counterparty: string;
  amount: string;
  currency: string;
  reference: string | null;
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
  const [transactions, setTx] = useState<Tx[]>([]);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [showBankPicker, setShowBankPicker] = useState(false);
  const [availableBanks, setAvailableBanks] = useState<ASPSP[]>([]);
  const [selectedBank, setSelectedBank] = useState<ASPSP | null>(null);

  const loadData = async () => {
    try {
      const [accs, txs] = await Promise.all([
        api<Account[]>("/banking/accounts"),
        api<Tx[]>("/banking/transactions"),
      ]);
      setAccounts(accs);
      setTx(txs);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load banking data");
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
        // Default to a mock bank if available, else the first bank
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
              {availableBanks.map((bank) => {
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

      <div className="section-heading">Accounts</div>
      {accounts.length === 0 ? (
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
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", color: "var(--muted)", padding: "24px" }}>
                  No transactions yet. Connect a bank account to see transactions.
                </td>
              </tr>
            ) : (
              transactions.map((t) => (
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
                    <span className="status">Unmatched</span>
                  </td>
                </tr>
              ))
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
