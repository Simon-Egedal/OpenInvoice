"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ShieldCheck, UserCheck } from "lucide-react";
import { api, SetupStatus } from "@/lib/api";

export default function SetupAdminPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<SetupStatus>("/setup/status")
      .then((status) => {
        if (!status.complete || !status.applied) {
          router.replace("/setup");
          return;
        }
        if (!status.has_organization) {
          router.replace("/setup/organization");
          return;
        }
        if (status.has_admin) {
          router.replace("/");
          return;
        }
        if (status.organization_name) {
          setOrgName(status.organization_name);
        }
        setLoading(false);
      })
      .catch(() => {
        router.replace("/setup");
      });
  }, [router]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (password.length < 12) {
      setError("Password must be at least 12 characters");
      return;
    }
    setBusy(true);
    setError("");

    try {
      await api("/setup/admin", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
        }),
      });

      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create administrator account");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="page setup-page">
        <p>Loading admin setup…</p>
      </div>
    );
  }

  return (
    <div className="page setup-page">
      <Brand />
      <div className="setup-intro">
        <div className="setup-eyebrow">
          <ShieldCheck size={14} /> STEP 3 OF 3 • ADMINISTRATOR
        </div>
        <h1 className="page-title">Create admin account</h1>
        <p className="page-description">
          Create the primary owner account for {orgName ? <strong>{orgName}</strong> : "your organization"}.
          You will use this account to sign in and manage your workspace.
        </p>
      </div>

      <form onSubmit={submit} className="setup-form" style={{ paddingTop: 20 }}>
        <div style={{ display: "grid", gap: 20, maxWidth: 520 }}>
          <label className="field full">
            <span>Your full name</span>
            <input
              name="full_name"
              placeholder="e.g. Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoComplete="name"
              autoFocus
            />
          </label>

          <label className="field full">
            <span>Email address</span>
            <input
              name="email"
              type="email"
              placeholder="jane@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>

          <label className="field full">
            <span>Password</span>
            <input
              name="password"
              type="password"
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            <small className="page-description" style={{ marginTop: 2 }}>
              At least 12 characters. Use a strong passphrase or password manager.
            </small>
          </label>

          {error && <p className="error-text" role="alert">{error}</p>}

          <div style={{ paddingTop: 10 }}>
            <button disabled={busy} className="button button-primary setup-submit" type="submit">
              {busy ? "Creating account…" : "Complete setup"}
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function Brand() {
  return (
    <div className="setup-brand">
      <span className="brand-mark">O</span>OpenInvoice
    </div>
  );
}
