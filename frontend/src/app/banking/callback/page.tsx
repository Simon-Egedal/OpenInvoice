"use client";
import { formatMoney, scaled } from "@/lib/money";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useRef } from "react";
import { ArrowLeft, Check, Loader2, WalletCards } from "lucide-react";
import { api } from "@/lib/api";

type CallbackResult = {
  status: string;
  accounts_count: number;
  accounts: Array<{
    id: string;
    name: string;
    bank: string;
    masked_number: string;
    currency: string;
    balance: string;
  }>;
};

function CallbackContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const errorDesc = searchParams.get("error_description");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [accounts, setAccounts] = useState<CallbackResult["accounts"]>([]);
  const executedRef = useRef(false);

  useEffect(() => {
    if (error) {
      setStatus("error");
      setMessage(errorDesc || "The bank authorization was not completed or was cancelled.");
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("No authorization code was received from the bank.");
      return;
    }

    if (executedRef.current) return;
    executedRef.current = true;

    async function exchange() {
      try {
        const result = await api<CallbackResult>("/banking/connections/callback", {
          method: "POST",
          body: JSON.stringify({ code, state: searchParams.get("state") ?? "" }),
        });
        setStatus("success");
        setAccounts(result.accounts || []);
        setMessage(
          result.accounts_count > 0
            ? `Successfully connected ${result.accounts_count} bank account${result.accounts_count > 1 ? "s" : ""}.`
            : "Bank connection established successfully."
        );
      } catch (err) {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Failed to connect bank account.");
      }
    }

    exchange();
  }, [code, error, errorDesc]);

  return (
    <div className="page" style={{ maxWidth: 540, paddingTop: 60 }}>
      <div className="setup-success">
        <span
          className="setup-success-icon"
          style={{
            color:
              status === "loading"
                ? "var(--accent)"
                : status === "error"
                ? "#c53030"
                : "var(--accent)",
          }}
        >
          {status === "loading" ? (
            <Loader2 className="animate-spin" size={22} />
          ) : status === "error" ? (
            <WalletCards size={22} />
          ) : (
            <Check size={22} />
          )}
        </span>
        <h1 className="page-title">
          {status === "loading"
            ? "Connecting bank account…"
            : status === "error"
            ? "Connection failed"
            : "Bank account connected"}
        </h1>
        <p className="page-description">
          {status === "loading"
            ? "Exchanging authorization code and synchronizing your account data…"
            : message}
        </p>

        {status === "success" && accounts.length > 0 && (
          <div style={{ marginTop: 16, marginBottom: 16, textAlign: "left" }}>
            {accounts.map((a) => (
              <div
                key={a.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  borderRadius: "6px",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  marginBottom: 8,
                }}
              >
                <div>
                  <strong>{a.name}</strong>
                  <div style={{ fontSize: "0.85em", color: "var(--muted)" }}>
                    {a.bank} • {a.masked_number}
                  </div>
                </div>
                <div style={{ textAlign: "right", fontFamily: "monospace" }}>
                  {a.currency} {formatMoney(String(a.balance))}
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 24 }}>
          <Link className="button button-primary" href="/banking">
            <ArrowLeft size={14} /> Back to Banking
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function BankingCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="page" style={{ maxWidth: 540, paddingTop: 60 }}>
          <p>Processing bank authorization…</p>
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
