"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowLeft, Check, WalletCards } from "lucide-react";

function CallbackContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");

  useEffect(() => {
    if (error) {
      setStatus("error");
    } else if (code) {
      // Future provider exchange: currently acknowledge authorization
      setStatus("success");
    } else {
      setStatus("success");
    }
  }, [code, error]);

  return (
    <div className="page" style={{ maxWidth: 540, paddingTop: 60 }}>
      <div className="setup-success">
        <span className="setup-success-icon" style={{ color: status === "error" ? "var(--muted)" : "var(--accent)" }}>
          {status === "error" ? <WalletCards size={22} /> : <Check size={22} />}
        </span>
        <h1 className="page-title">{status === "error" ? "Bank connection cancelled" : "Authorization received"}</h1>
        <p className="page-description">
          {status === "error"
            ? (searchParams.get("error_description") || "The bank authorization was not completed.")
            : "Your bank authorization code has been received. You can return to your banking dashboard."}
        </p>
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
    <Suspense fallback={<div className="page" style={{ maxWidth: 540, paddingTop: 60 }}><p>Processing bank authorization…</p></div>}>
      <CallbackContent />
    </Suspense>
  );
}
