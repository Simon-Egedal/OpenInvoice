"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function AuthPage() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: data.email, password: data.password }),
      });
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 520, paddingTop: 75 }}>
      <Link href="/" className="brand" style={{ padding: 0, marginBottom: 34 }}>
        <span className="brand-mark">O</span>
        <span>OpenInvoice</span>
      </Link>
      <h1 className="page-title">Welcome back</h1>
      <p className="page-description" style={{ marginBottom: 25 }}>
        Sign in to your organization.
      </p>
      <form onSubmit={submit} className="form-grid">
        <div className="field full">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required autoComplete="email" autoFocus />
        </div>
        <div className="field full">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
          />
        </div>
        {error && (
          <p className="error-text field full" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary field full" disabled={busy}>
          {busy ? "Please wait…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
