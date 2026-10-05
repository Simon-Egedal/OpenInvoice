"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, Image as ImageIcon, Upload, X } from "lucide-react";
import { API, api, SetupStatus } from "@/lib/api";

export default function SetupOrganizationPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [country, setCountry] = useState("DK");
  const [currency, setCurrency] = useState("DKK");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<SetupStatus>("/setup/status")
      .then((status) => {
        if (!status.complete || !status.applied) {
          router.replace("/setup");
          return;
        }
        if (status.has_admin) {
          router.replace("/");
          return;
        }
        if (status.has_organization && status.organization_name) {
          setName(status.organization_name);
        }
        setLoading(false);
      })
      .catch(() => {
        router.replace("/setup");
      });
  }, [router]);

  function handleFileSelect(file: File) {
    if (!file.type.startsWith("image/") && !file.name.match(/\.(png|jpe?g|svg|webp|gif)$/i)) {
      setError("Please select an image file (PNG, JPG, SVG, WebP)");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Logo must be 5 MB or smaller");
      return;
    }
    setError("");
    setLogoFile(file);
    const objectUrl = URL.createObjectURL(file);
    setLogoPreview(objectUrl);
  }

  function handleRemoveLogo() {
    setLogoFile(null);
    if (logoPreview) {
      URL.revokeObjectURL(logoPreview);
      setLogoPreview(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Organization name is required");
      return;
    }
    setBusy(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("name", name.trim());
      formData.append("country", country.trim().toUpperCase());
      formData.append("currency", currency.trim().toUpperCase());
      if (logoFile) {
        formData.append("logo", logoFile);
      }

      const res = await fetch(`${API}/api/v1/setup/organization`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Failed to save organization (${res.status})`);
      }

      router.push("/setup/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save organization");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="page setup-page">
        <p>Loading organization setup…</p>
      </div>
    );
  }

  return (
    <div className="page setup-page">
      <Brand />
      <div className="setup-intro">
        <div className="setup-eyebrow">
          <Building2 size={14} /> STEP 2 OF 3 • ORGANIZATION
        </div>
        <h1 className="page-title">Set up your organization</h1>
        <p className="page-description">
          Enter your organization name and upload a logo. These will appear on invoices, emails, and in the application header.
        </p>
      </div>

      <form onSubmit={submit} className="setup-form" style={{ paddingTop: 20 }}>
        <div style={{ display: "grid", gap: 20, maxWidth: 580 }}>
          <label className="field full">
            <span>Organization name</span>
            <input
              name="name"
              placeholder="e.g. Acme Studio"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </label>

          <div className="field full">
            <label>Organization logo</label>
            <input
              type="file"
              ref={fileInputRef}
              accept="image/png,image/jpeg,image/svg+xml,image/webp"
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileSelect(file);
              }}
            />

            {logoPreview ? (
              <div className="logo-preview-box">
                <img src={logoPreview} alt="Logo preview" className="logo-preview-thumb" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {logoFile?.name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                    {logoFile ? `${(logoFile.size / 1024).toFixed(1)} KB` : "Uploaded logo"}
                  </div>
                </div>
                <button
                  type="button"
                  className="button"
                  onClick={() => fileInputRef.current?.click()}
                  style={{ fontSize: 11, padding: "5px 10px" }}
                >
                  Change
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={handleRemoveLogo}
                  title="Remove logo"
                  aria-label="Remove logo"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div
                className="logo-dropzone"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleFileSelect(file);
                }}
              >
                <div style={{ display: "inline-grid", placeItems: "center", width: 40, height: 40, borderRadius: 6, background: "#edf1ee", color: "var(--accent)", marginBottom: 8 }}>
                  <Upload size={18} />
                </div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Click or drag logo image here</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                  PNG, JPG, SVG, or WebP up to 5 MB
                </div>
              </div>
            )}
          </div>

          <div className="setup-grid">
            <label className="field">
              <span>Country</span>
              <input
                name="country"
                maxLength={2}
                value={country}
                onChange={(e) => setCountry(e.target.value.toUpperCase())}
                placeholder="DK"
                required
              />
            </label>
            <label className="field">
              <span>Currency</span>
              <input
                name="currency"
                maxLength={3}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="DKK"
                required
              />
            </label>
          </div>

          {error && <p className="error-text" role="alert">{error}</p>}

          <div style={{ paddingTop: 10 }}>
            <button disabled={busy} className="button button-primary setup-submit" type="submit">
              {busy ? "Saving…" : "Continue to admin account"}
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
