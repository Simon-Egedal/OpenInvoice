"use client";

import { useEffect, useState } from "react";
import { Check, Upload } from "lucide-react";
import { API, api, CurrentUser, Organization } from "@/lib/api";

const CURRENCIES = ["DKK", "EUR", "USD", "GBP", "SEK", "NOK", "CHF"];

export function OrganizationSettings() {
  const [loadingOrg, setLoadingOrg] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  // Organization states
  const [org, setOrg] = useState<Organization | null>(null);
  const [orgName, setOrgName] = useState("");
  const [orgCountry, setOrgCountry] = useState("DK");
  const [orgCurrency, setOrgCurrency] = useState("DKK");
  const [billing, setBilling] = useState({address: "", postal_code: "", city: "", vat_number: "", payment_information: "", payment_terms: "", invoice_prefix: "INV"});
  const [customCurrency, setCustomCurrency] = useState("");
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [orgBusy, setOrgBusy] = useState(false);
  const [orgError, setOrgError] = useState("");
  const [orgSuccess, setOrgSuccess] = useState("");

  useEffect(() => {
    api<CurrentUser>("/auth/me").then(user => setIsAdmin(["owner", "admin"].includes(user.role))).catch(e => setOrgError(e instanceof Error ? e.message : "Unable to check organization permissions"));
  }, []);

  // Load Organization
  useEffect(() => {
    api<Organization>("/organizations/current")
      .then((data) => {
        setOrg(data);
        setOrgName(data.name);
        setOrgCountry(data.country);
        setBilling({address: data.address ?? "", postal_code: data.postal_code ?? "", city: data.city ?? "", vat_number: data.vat_number ?? "", payment_information: data.payment_information ?? "", payment_terms: data.payment_terms ?? "", invoice_prefix: data.invoice_prefix ?? "INV"});
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
      .catch(e => setOrgError(e instanceof Error ? e.message : "Unable to load organization"))
      .finally(() => {
        setLoadingOrg(false);
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
          ...billing,
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

  return (
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

              <div className="setup-grid">
                {([ ["address", "Seller address"], ["postal_code", "Postal code"], ["city", "City"], ["vat_number", "VAT number"], ["invoice_prefix", "Invoice number prefix"] ] as const).map(([key, label]) => <Field key={key} label={label}><input value={billing[key]} disabled={!isAdmin} maxLength={key === "invoice_prefix" ? 20 : key === "address" ? 300 : key === "postal_code" ? 30 : key === "city" ? 100 : 80} required={key === "invoice_prefix"} pattern={key === "invoice_prefix" ? "[A-Za-z0-9-]{1,20}" : undefined} onChange={e => setBilling(current => ({...current, [key]: e.target.value}))}/></Field>)}
              </div>
              <Field label="Bank and payment information"><textarea value={billing.payment_information} disabled={!isAdmin} maxLength={2000} onChange={e => setBilling(current => ({...current, payment_information: e.target.value}))}/></Field>
              <Field label="Payment terms"><textarea value={billing.payment_terms} disabled={!isAdmin} maxLength={2000} onChange={e => setBilling(current => ({...current, payment_terms: e.target.value}))}/></Field>

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
