"use client";
import { useEffect, useState } from "react";
import { ArrowRight, Check, Database, HardDrive, Mail, ShieldAlert, ShieldCheck, WalletCards } from "lucide-react";
import { api, InfrastructureConfig } from "@/lib/api";

export default function Settings() {
  const [sessionMessage, setSessionMessage] = useState("");
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [config, setConfig] = useState<InfrastructureConfig | null>(null);

  // Form states
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
          <p className="page-description">Manage your OpenInvoice session and self-hosted infrastructure credentials.</p>
        </div>
      </header>

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
                      <input type="number" value={dbPort} onChange={(e) => setDbPort(Number(e.target.value))} required />
                    </Field>
                    <Field label="Database name">
                      <input value={dbName} onChange={(e) => setDbName(e.target.value)} required />
                    </Field>
                    <Field label="Username">
                      <input value={dbUsername} onChange={(e) => setDbUsername(e.target.value)} required />
                    </Field>
                    <Field label="Password">
                      <input
                        type="password"
                        value={dbPassword}
                        onChange={(e) => setDbPassword(e.target.value)}
                        placeholder={config?.has_database_password ? "•••••••• (unchanged)" : "Enter password"}
                        autoComplete="new-password"
                      />
                    </Field>
                  </div>
                  <label className="check-field">
                    <input type="checkbox" checked={dbSsl} onChange={(e) => setDbSsl(e.target.checked)} />
                    Require TLS for database connection
                  </label>
                </>
              )}
            </div>

            {/* Banking Provider Section */}
            <SetupSection
              icon={<WalletCards size={17} />}
              title="Banking Provider"
              detail="Choose between demo/mock banking data or Enable Banking integration adapter."
            />
            <div className="setup-fields">
              <Field label="Banking provider">
                <select value={bankingProvider} onChange={(e) => setBankingProvider(e.target.value as "mock" | "enable_banking")}>
                  <option value="mock">Mock banking (recommended)</option>
                  <option value="enable_banking">Enable Banking</option>
                </select>
              </Field>
              {bankingProvider === "enable_banking" && (
                <div className="setup-grid">
                  <Field label="Enable Banking application ID">
                    <input
                      value={enableBankingAppId}
                      onChange={(e) => setEnableBankingAppId(e.target.value)}
                      placeholder="app_12345678"
                      required
                    />
                  </Field>
                  <Field label="Private key path inside API container">
                    <input
                      value={enableBankingKeyPath}
                      onChange={(e) => setEnableBankingKeyPath(e.target.value)}
                      placeholder="/run/secrets/enable-banking.pem"
                      required
                    />
                  </Field>
                </div>
              )}
            </div>

            {/* Email Provider Section */}
            <SetupSection
              icon={<Mail size={17} />}
              title="Email Delivery"
              detail="Configure SMTP delivery for sending invoices or keep messages in API logs."
            />
            <div className="setup-fields">
              <Field label="Email provider">
                <select value={emailProvider} onChange={(e) => setEmailProvider(e.target.value as "console" | "smtp")}>
                  <option value="console">Console (development)</option>
                  <option value="smtp">SMTP server</option>
                </select>
              </Field>
              {emailProvider === "console" ? (
                <p className="setup-hint">Outgoing emails are logged in the API console and are not sent to recipients.</p>
              ) : (
                <div className="setup-grid">
                  <Field label="SMTP host">
                    <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.example.com" required />
                  </Field>
                  <Field label="Port">
                    <input type="number" value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} required />
                  </Field>
                  <Field label="Username">
                    <input value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)} autoComplete="username" />
                  </Field>
                  <Field label="Password">
                    <input
                      type="password"
                      value={smtpPassword}
                      onChange={(e) => setSmtpPassword(e.target.value)}
                      placeholder={config?.has_smtp_password ? "•••••••• (unchanged)" : "Enter SMTP password"}
                      autoComplete="new-password"
                    />
                  </Field>
                  <Field label="From address">
                    <input value={smtpFrom} onChange={(e) => setSmtpFrom(e.target.value)} placeholder="Invoices <billing@example.com>" required />
                  </Field>
                  <label className="check-field" style={{ alignSelf: "center", marginTop: 18 }}>
                    <input type="checkbox" checked={smtpUseTls} onChange={(e) => setSmtpUseTls(e.target.checked)} />
                    Use STARTTLS
                  </label>
                </div>
              )}
            </div>

            {/* Storage Provider Section */}
            <SetupSection
              icon={<HardDrive size={17} />}
              title="Document Storage"
              detail="Store invoice PDFs and organization logos locally on volume or in an S3 bucket."
            />
            <div className="setup-fields">
              <Field label="Storage provider">
                <select value={storageProvider} onChange={(e) => setStorageProvider(e.target.value as "local" | "s3")}>
                  <option value="local">Local filesystem volume</option>
                  <option value="s3">S3-compatible bucket</option>
                </select>
              </Field>
              {storageProvider === "local" ? (
                <p className="setup-hint">Files are saved to the persistent Docker data volume.</p>
              ) : (
                <div className="setup-grid">
                  <Field label="S3 endpoint (optional)">
                    <input value={s3Endpoint} onChange={(e) => setS3Endpoint(e.target.value)} placeholder="https://s3.example.com" />
                  </Field>
                  <Field label="Region">
                    <input value={s3Region} onChange={(e) => setS3Region(e.target.value)} placeholder="eu-central-1" required />
                  </Field>
                  <Field label="Bucket name">
                    <input value={s3Bucket} onChange={(e) => setS3Bucket(e.target.value)} placeholder="my-invoice-bucket" required />
                  </Field>
                  <Field label="Access key ID">
                    <input value={s3AccessKeyId} onChange={(e) => setS3AccessKeyId(e.target.value)} required />
                  </Field>
                  <Field label="Secret access key">
                    <input
                      type="password"
                      value={s3SecretKey}
                      onChange={(e) => setS3SecretKey(e.target.value)}
                      placeholder={config?.has_s3_secret ? "•••••••• (unchanged)" : "Enter secret access key"}
                      autoComplete="new-password"
                    />
                  </Field>
                </div>
              )}
            </div>

            {/* Security Section */}
            <SetupSection
              icon={<ShieldCheck size={17} />}
              title="Security & Sessions"
              detail="Session cookies and encryption on the persistent application volume."
            />
            <div className="setup-fields">
              <label className="check-field">
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
