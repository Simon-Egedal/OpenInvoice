"use client";

import { useEffect, useState } from "react";
import {
  ArrowRight,
  Building2,
  Check,
  Database,
  HardDrive,
  Mail,
  ShieldAlert,
  ShieldCheck,
  Upload,
  WalletCards,
  X,
} from "lucide-react";
import { API, api, InfrastructureConfig, Organization } from "@/lib/api";

const CURRENCIES = ["DKK", "EUR", "USD", "GBP", "SEK", "NOK", "CHF"];

export default function Settings() {
  const [sessionMessage, setSessionMessage] = useState("");
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadingOrg, setLoadingOrg] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [config, setConfig] = useState<InfrastructureConfig | null>(null);

  // Organization states
  const [org, setOrg] = useState<Organization | null>(null);
  const [orgName, setOrgName] = useState("");
  const [orgCountry, setOrgCountry] = useState("DK");
  const [orgCurrency, setOrgCurrency] = useState("DKK");
  const [customCurrency, setCustomCurrency] = useState("");
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [orgBusy, setOrgBusy] = useState(false);
  const [orgError, setOrgError] = useState("");
  const [orgSuccess, setOrgSuccess] = useState("");

  // Infrastructure Form states
  const [dbMode, setDbMode] = useState<"bundled" | "external">("bundled");
  const [dbHost, setDbHost] = useState("localhost");
  const [dbPort, setDbPort] = useState(5432);
  const [dbName, setDbName] = useState("openinvoice");
  const [dbUsername, setDbUsername] = useState("openinvoice");
  const [dbPassword, setDbPassword] = useState("");
  const [dbSsl, setDbSsl] = useState(false);

  const [emailProvider, setEmailProvider] = useState<"console" | "smtp">("console");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFrom, setSmtpFrom] = useState("OpenInvoice <invoices@example.com>");
  const [smtpUseTls, setSmtpUseTls] = useState(true);

  const [storageProvider, setStorageProvider] = useState<"local" | "s3">("local");
  const [s3Endpoint, setS3Endpoint] = useState("");
  const [s3Bucket, setS3Bucket] = useState("");
  const [s3AccessKeyId, setS3AccessKeyId] = useState("");
  const [s3SecretKey, setS3SecretKey] = useState("");
  const [s3Region, setS3Region] = useState("eu-central-1");

  const [bankingProvider, setBankingProvider] = useState<"mock" | "enable_banking">("mock");
  const [enableBankingAppId, setEnableBankingAppId] = useState("");
  const [enableBankingKeyPath, setEnableBankingKeyPath] = useState("");

  const [cookieSecure, setCookieSecure] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [restartNotice, setRestartNotice] = useState(false);

  // Load Organization
  useEffect(() => {
    api<Organization>("/organizations/current")
      .then((data) => {
        setOrg(data);
        setOrgName(data.name);
        setOrgCountry(data.country);
        const curr = data.currency || "DKK";
        if (CURRENCIES.includes(curr)) {
          setOrgCurrency(curr);
          setCustomCurrency("");
        } else {
          setOrgCurrency("OTHER");
          setCustomCurrency(curr);
        }
        if (data.logo_key) {
          setLogoPreview(`${API}/api/v1/organizations/${data.id}/logo`);
        }
      })
      .catch(() => {})
      .finally(() => {
        setLoadingOrg(false);
      });
  }, []);

  // Load Infrastructure Config
  useEffect(() => {
    api<InfrastructureConfig>("/settings/infrastructure")
      .then((cfg) => {
        setIsAdmin(true);
        setConfig(cfg);
        setDbMode(cfg.database_mode);
        setDbHost(cfg.database_host);
        setDbPort(cfg.database_port);
        setDbName(cfg.database_name);
        setDbUsername(cfg.database_username);
        setDbSsl(cfg.database_ssl);

        setEmailProvider(cfg.email_provider);
        setSmtpHost(cfg.smtp_host);
        setSmtpPort(cfg.smtp_port);
        setSmtpUsername(cfg.smtp_username);
        setSmtpFrom(cfg.smtp_from || "OpenInvoice <invoices@example.com>");
        setSmtpUseTls(cfg.smtp_use_tls);

        setStorageProvider(cfg.storage_provider);
        setS3Endpoint(cfg.s3_endpoint_url);
        setS3Bucket(cfg.s3_bucket);
        setS3AccessKeyId(cfg.s3_access_key_id);
        setS3Region(cfg.s3_region || "eu-central-1");

        setBankingProvider(cfg.banking_provider);
        setEnableBankingAppId(cfg.enable_banking_app_id);
        setEnableBankingKeyPath(cfg.enable_banking_private_key_path);

        setCookieSecure(cfg.session_cookie_secure);
        setRestartNotice(cfg.restart_required);
      })
      .catch(() => {
        setIsAdmin(false);
      })
      .finally(() => {
        setLoadingConfig(false);
      });
  }, []);

  async function handleSaveOrganization(e: React.FormEvent) {
    e.preventDefault();
    setOrgBusy(true);
    setOrgError("");
    setOrgSuccess("");

    const finalCurrency = (orgCurrency === "OTHER" ? customCurrency : orgCurrency).trim().toUpperCase();
    if (!finalCurrency) {
      setOrgError("Please specify a currency code.");
      setOrgBusy(false);
      return;
    }

    try {
      // 1. Update name, country, currency
      const updatedOrg = await api<Organization>("/organizations/current", {
        method: "PATCH",
        body: JSON.stringify({
          name: orgName.trim(),
          country: orgCountry.trim().toUpperCase(),
          currency: finalCurrency,
        }),
      });

      // 2. Handle logo changes if any
      if (logoFile) {
        const formData = new FormData();
        formData.append("logo", logoFile);
        const res = await fetch(`${API}/api/v1/organizations/current/logo`, {
          method: "POST",
          body: formData,
          credentials: "include",
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? "Failed to upload logo");
        }
        const withLogo = await res.json();
        setOrg(withLogo);
        setLogoPreview(`${API}/api/v1/organizations/${withLogo.id}/logo?t=${Date.now()}`);
        setLogoFile(null);
      } else if (removeLogo) {
        await api("/organizations/current/logo", { method: "DELETE" });
        setOrg({ ...updatedOrg, logo_key: null, logo_url: null });
        setLogoPreview(null);
        setRemoveLogo(false);
      } else {
        setOrg(updatedOrg);
      }

      setOrgSuccess("Organization profile updated successfully.");
      window.dispatchEvent(new Event("organizationUpdated"));
    } catch (err) {
      setOrgError(err instanceof Error ? err.message : "Failed to update organization profile");
    } finally {
      setOrgBusy(false);
    }
  }

  function handleLogoFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setOrgError("Logo file must be smaller than 5 MB");
      return;
    }
    setLogoFile(file);
    setLogoPreview(URL.createObjectURL(file));
    setRemoveLogo(false);
    setOrgError("");
  }

  function handleRemoveLogo() {
    setLogoFile(null);
    setLogoPreview(null);
    setRemoveLogo(true);
  }

  async function handleSaveInfrastructure(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");

    const payload = {
      database_mode: dbMode,
      database_host: dbHost.trim(),
      database_port: Number(dbPort),
      database_name: dbName.trim(),
      database_username: dbUsername.trim(),
      database_password: dbPassword,
      database_ssl: dbSsl,
      email_provider: emailProvider,
      smtp_host: smtpHost.trim(),
      smtp_port: Number(smtpPort),
      smtp_username: smtpUsername.trim(),
      smtp_password: smtpPassword,
      smtp_from: smtpFrom.trim(),
      smtp_use_tls: smtpUseTls,
      storage_provider: storageProvider,
      s3_endpoint_url: s3Endpoint.trim(),
      s3_bucket: s3Bucket.trim(),
      s3_access_key_id: s3AccessKeyId.trim(),
      s3_secret_access_key: s3SecretKey,
      s3_region: s3Region.trim(),
      banking_provider: bankingProvider,
      enable_banking_app_id: enableBankingAppId.trim(),
      enable_banking_private_key_path: enableBankingKeyPath.trim(),
      session_cookie_secure: cookieSecure,
    };

    try {
      const updated = await api<InfrastructureConfig>("/settings/infrastructure", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setConfig(updated);
      setDbPassword("");
      setSmtpPassword("");
      setS3SecretKey("");
      setSuccess("Infrastructure configuration saved successfully.");
      setRestartNotice(updated.restart_required);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save infrastructure configuration");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <header className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-description">Manage your organization profile, session, and self-hosted infrastructure credentials.</p>
        </div>
      </header>

      {/* Organization Profile Section */}
      <section style={{ padding: "18px 0 28px", borderTop: "1px solid var(--line)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <div className="section-heading" style={{ margin: 0 }}>Organization Profile</div>
        </div>
        <p className="page-description" style={{ marginBottom: 20 }}>
          Manage your organization name, default currency, country, and logo.
        </p>

        {loadingOrg ? (
          <p className="page-description">Loading organization…</p>
        ) : (
          <form onSubmit={handleSaveOrganization} className="setup-form">
            <div className="setup-fields">
              <Field label="Organization name">
                <input
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Acme Corporation"
                  required
                  disabled={!isAdmin}
                />
              </Field>

              <div className="setup-grid">
                <Field label="Default currency">
                  <div style={{ display: "flex", gap: 8 }}>
                    <select
                      value={orgCurrency}
                      onChange={(e) => setOrgCurrency(e.target.value)}
                      disabled={!isAdmin}
                      style={{ minWidth: 160 }}
                    >
                      <option value="DKK">DKK — Danish Krone</option>
                      <option value="EUR">EUR — Euro</option>
                      <option value="USD">USD — US Dollar</option>
                      <option value="GBP">GBP — British Pound</option>
                      <option value="SEK">SEK — Swedish Krona</option>
                      <option value="NOK">NOK — Norwegian Krone</option>
                      <option value="CHF">CHF — Swiss Franc</option>
                      <option value="OTHER">Custom code…</option>
                    </select>
                    {orgCurrency === "OTHER" && (
                      <input
                        value={customCurrency}
                        onChange={(e) => setCustomCurrency(e.target.value.toUpperCase())}
                        placeholder="e.g. CAD"
                        maxLength={10}
                        required
                        disabled={!isAdmin}
                        style={{ maxWidth: 110 }}
                      />
                    )}
                  </div>
                </Field>

                <Field label="Country code">
                  <input
                    value={orgCountry}
                    onChange={(e) => setOrgCountry(e.target.value.toUpperCase())}
                    placeholder="DK"
                    maxLength={2}
                    required
                    disabled={!isAdmin}
                    style={{ maxWidth: 100 }}
                  />
                </Field>
              </div>

              {/* Logo section */}
              <div className="field">
                <label>Organization logo</label>
                <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 6 }}>
                  {logoPreview ? (
                    <div
                      style={{
                        width: 64,
                        height: 64,
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        overflow: "hidden",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "#fff",
                        padding: 4,
                      }}
                    >
                      <img
                        src={logoPreview}
                        alt={orgName}
                        style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                      />
                    </div>
                  ) : (
                    <div
                      style={{
                        width: 64,
                        height: 64,
                        borderRadius: 8,
                        border: "1px dashed var(--border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "var(--surface)",
                        color: "var(--muted)",
                        fontWeight: 600,
                        fontSize: "1.2rem",
                      }}
                    >
                      {(orgName?.[0] || "O").toUpperCase()}
                    </div>
                  )}

                  {isAdmin && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <label
                        className="button"
                        style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, margin: 0 }}
                      >
                        <Upload size={14} /> Upload logo
                        <input
                          type="file"
                          accept="image/*"
                          style={{ display: "none" }}
                          onChange={handleLogoFileChange}
                        />
                      </label>
                      {logoPreview && (
                        <button
                          type="button"
                          className="button button-subtle"
                          style={{ fontSize: 12, padding: "4px 8px" }}
                          onClick={handleRemoveLogo}
                        >
                          Remove logo
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {orgError && <p className="error-text" role="alert">{orgError}</p>}
              {orgSuccess && (
                <div className="notice" role="status" style={{ color: "var(--accent)", background: "var(--accent-wash)" }}>
                  <Check size={14} style={{ display: "inline", verticalAlign: "middle", marginRight: 6 }} />
                  {orgSuccess}
                </div>
              )}

              {isAdmin ? (
                <div style={{ marginTop: 14 }}>
                  <button className="button button-primary" type="submit" disabled={orgBusy}>
                    {orgBusy ? "Saving…" : "Save organization"}
                  </button>
                </div>
              ) : (
                <p className="setup-hint">Only administrators can edit organization details.</p>
              )}
            </div>
          </form>
        )}
      </section>

      {/* Session Section */}
      <section style={{ padding: "18px 0 28px", borderTop: "1px solid var(--line)" }}>
        <div className="section-heading">Session</div>
        <p className="page-description" style={{ marginBottom: 14 }}>
          Sign out of your current account on this device.
        </p>
        <button
          className="button"
          onClick={async () => {
            await api("/auth/logout", { method: "POST" });
            setSessionMessage("You have been signed out. Refresh the page to sign in.");
          }}
        >
          Sign out
        </button>
        {sessionMessage && <p className="notice" style={{ marginTop: 12 }} role="status">{sessionMessage}</p>}
      </section>

      {/* Infrastructure Section */}
      <section style={{ padding: "24px 0", borderTop: "1px solid var(--line)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <div className="section-heading" style={{ margin: 0 }}>Infrastructure & Onboarding Credentials</div>
          {isAdmin && (
            <span style={{ fontSize: 10, letterSpacing: ".06em", color: "var(--accent)", fontWeight: 700, padding: "2px 6px", background: "var(--accent-wash)", borderRadius: 4 }}>
              ADMINISTRATOR
            </span>
          )}
        </div>
        <p className="page-description" style={{ marginBottom: 20 }}>
          Manage the connections, storage provider, banking integration, and email delivery configured during onboarding.
        </p>

        {loadingConfig && <p className="page-description">Loading configuration…</p>}

        {!loadingConfig && !isAdmin && (
          <div className="notice" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <ShieldAlert size={16} />
            <span>Only organization administrators can view and update infrastructure credentials.</span>
          </div>
        )}

        {!loadingConfig && isAdmin && (
          <form onSubmit={handleSaveInfrastructure} className="setup-form">
            {restartNotice && (
              <div className="notice setup-command" style={{ margin: "16px 0 20px" }}>
                <strong>Restart Required</strong>
                <p style={{ margin: "4px 0 8px", fontSize: 12 }}>
                  Certain configuration changes (such as database or storage path) require restarting the API container to take effect:
                </p>
                <code>docker compose restart api</code>
              </div>
            )}

            {/* Database Section */}
            <SetupSection
              icon={<Database size={17} />}
              title="Database"
              detail="PostgreSQL stores your organizations, invoices, contacts, and activity logs."
            />
            <div className="setup-fields">
              <Field label="PostgreSQL setup">
                <select value={dbMode} onChange={(e) => setDbMode(e.target.value as "bundled" | "external")}>
                  <option value="bundled">Bundled PostgreSQL (recommended)</option>
                  <option value="external">External PostgreSQL server</option>
                </select>
              </Field>
              {dbMode === "bundled" ? (
                <p className="setup-hint">Uses the PostgreSQL container from Docker Compose.</p>
              ) : (
                <>
                  <div className="setup-grid">
                    <Field label="Host">
                      <input value={dbHost} onChange={(e) => setDbHost(e.target.value)} placeholder="db.example.com" required />
                    </Field>
                    <Field label="Port">
                      <input type="number" value={dbPort} onChange={(e) => setDbPort(Number(e.target.value))} min={1} max={65535} required />
                    </Field>
                  </div>
                  <div className="setup-grid">
                    <Field label="Database name">
                      <input value={dbName} onChange={(e) => setDbName(e.target.value)} required />
                    </Field>
                    <Field label="Username">
                      <input value={dbUsername} onChange={(e) => setDbUsername(e.target.value)} required />
                    </Field>
                  </div>
                  <Field label="Password">
                    <input
                      type="password"
                      value={dbPassword}
                      onChange={(e) => setDbPassword(e.target.value)}
                      placeholder={config?.has_database_password ? "•••••••• (leave blank to keep current)" : "Database password"}
                    />
                  </Field>
                  <label className="setup-checkbox">
                    <input type="checkbox" checked={dbSsl} onChange={(e) => setDbSsl(e.target.checked)} />
                    Require SSL for PostgreSQL connection
                  </label>
                </>
              )}
            </div>

            {/* Email Section */}
            <SetupSection
              icon={<Mail size={17} />}
              title="Email delivery"
              detail="Send invoices, reminders, and delivery receipts to customers."
            />
            <div className="setup-fields">
              <Field label="Email provider">
                <select value={emailProvider} onChange={(e) => setEmailProvider(e.target.value as "console" | "smtp")}>
                  <option value="console">Console (development / logs only)</option>
                  <option value="smtp">SMTP server</option>
                </select>
              </Field>
              {emailProvider === "console" ? (
                <p className="setup-hint">Outgoing emails will be written to stdout and captured in activity logs.</p>
              ) : (
                <>
                  <div className="setup-grid">
                    <Field label="SMTP Host">
                      <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.mailgun.org" required />
                    </Field>
                    <Field label="SMTP Port">
                      <input type="number" value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} min={1} max={65535} required />
                    </Field>
                  </div>
                  <div className="setup-grid">
                    <Field label="Username">
                      <input value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)} />
                    </Field>
                    <Field label="Password">
                      <input
                        type="password"
                        value={smtpPassword}
                        onChange={(e) => setSmtpPassword(e.target.value)}
                        placeholder={config?.has_smtp_password ? "•••••••• (leave blank to keep current)" : "SMTP password"}
                      />
                    </Field>
                  </div>
                  <Field label="From address">
                    <input value={smtpFrom} onChange={(e) => setSmtpFrom(e.target.value)} placeholder="Invoices <invoices@example.com>" required />
                  </Field>
                  <label className="setup-checkbox">
                    <input type="checkbox" checked={smtpUseTls} onChange={(e) => setSmtpUseTls(e.target.checked)} />
                    Use STARTTLS
                  </label>
                </>
              )}
            </div>

            {/* Storage Section */}
            <SetupSection
              icon={<HardDrive size={17} />}
              title="Document storage"
              detail="Store invoice PDFs and organization logos locally on volume or in an S3 bucket."
            />
            <div className="setup-fields">
              <Field label="Storage provider">
                <select value={storageProvider} onChange={(e) => setStorageProvider(e.target.value as "local" | "s3")}>
                  <option value="local">Local volume storage</option>
                  <option value="s3">Amazon S3 / S3-compatible</option>
                </select>
              </Field>
              {storageProvider === "local" ? (
                <p className="setup-hint">Files are stored securely on the persistent Docker application volume.</p>
              ) : (
                <>
                  <div className="setup-grid">
                    <Field label="Bucket name">
                      <input value={s3Bucket} onChange={(e) => setS3Bucket(e.target.value)} placeholder="my-company-invoices" required />
                    </Field>
                    <Field label="Region">
                      <input value={s3Region} onChange={(e) => setS3Region(e.target.value)} placeholder="eu-central-1" required />
                    </Field>
                  </div>
                  <Field label="Custom endpoint (optional for MinIO, Cloudflare R2, Wasabi)">
                    <input value={s3Endpoint} onChange={(e) => setS3Endpoint(e.target.value)} placeholder="https://<account-id>.r2.cloudflarestorage.com" />
                  </Field>
                  <div className="setup-grid">
                    <Field label="Access key ID">
                      <input value={s3AccessKeyId} onChange={(e) => setS3AccessKeyId(e.target.value)} required />
                    </Field>
                    <Field label="Secret access key">
                      <input
                        type="password"
                        value={s3SecretKey}
                        onChange={(e) => setS3SecretKey(e.target.value)}
                        placeholder={config?.has_s3_secret ? "•••••••• (leave blank to keep current)" : "AWS secret key"}
                      />
                    </Field>
                  </div>
                </>
              )}
            </div>

            {/* Banking Provider Section */}
            <SetupSection
              icon={<WalletCards size={17} />}
              title="Banking integration"
              detail="Live open banking synchronization or local simulated provider."
            />
            <div className="setup-fields">
              <Field label="Banking provider">
                <select value={bankingProvider} onChange={(e) => setBankingProvider(e.target.value as "mock" | "enable_banking")}>
                  <option value="mock">Demo / Mock banking (instant demo transactions)</option>
                  <option value="enable_banking">Enable Banking (live open banking PSD2)</option>
                </select>
              </Field>
              {bankingProvider === "mock" ? (
                <p className="setup-hint">Simulates bank connections and transactions without requiring third-party credentials.</p>
              ) : (
                <>
                  <Field label="Enable Banking Application ID">
                    <input
                      value={enableBankingAppId}
                      onChange={(e) => setEnableBankingAppId(e.target.value)}
                      placeholder="e.g. bcbc8a09-2e49-40ab-a9ae-d9ffe6f1dbb7"
                      required
                    />
                  </Field>
                  <Field label="Private key file path (.pem)">
                    <input
                      value={enableBankingKeyPath}
                      onChange={(e) => setEnableBankingKeyPath(e.target.value)}
                      placeholder="/run/secrets/enable-banking.pem"
                      required
                    />
                  </Field>
                  <p className="setup-hint">
                    Place your private key in the <code>secrets/</code> folder. It is mounted inside the container at <code>/run/secrets/enable-banking.pem</code>.
                  </p>
                </>
              )}
            </div>

            {/* Security Section */}
            <SetupSection
              icon={<ShieldCheck size={17} />}
              title="Security & cookies"
              detail="Cookie security flags for production deployments."
            />
            <div className="setup-fields">
              <label className="setup-checkbox">
                <input type="checkbox" checked={cookieSecure} onChange={(e) => setCookieSecure(e.target.checked)} />
                Serve secure session cookies (enable when using HTTPS)
              </label>
            </div>

            {/* Messages & Actions */}
            {error && <p className="error-text" role="alert" style={{ marginTop: 18 }}>{error}</p>}
            {success && (
              <div className="notice" role="status" style={{ marginTop: 18, color: "var(--accent)", background: "var(--accent-wash)" }}>
                <Check size={14} style={{ display: "inline", verticalAlign: "middle", marginRight: 6 }} />
                {success}
              </div>
            )}

            <div style={{ marginTop: 24 }}>
              <button disabled={busy} className="button button-primary setup-submit" type="submit">
                {busy ? "Validating & saving…" : "Save infrastructure settings"}
                <ArrowRight size={15} />
              </button>
            </div>
            <p className="setup-footnote">
              Connections to the database, SMTP server, and S3 bucket are tested and validated before new credentials are encrypted.
            </p>
          </form>
        )}
      </section>
    </div>
  );
}

function SetupSection({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return (
    <div className="setup-section">
      <span className="setup-section-icon">{icon}</span>
      <div>
        <h2>{title}</h2>
        <p>{detail}</p>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
