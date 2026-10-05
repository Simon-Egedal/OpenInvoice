"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API, api, Invoice, Organization, SetupStatus } from "@/lib/api";
import { Activity, Building2, ChevronDown, FileText, LayoutDashboard, LogIn, Menu, Settings, Users, WalletCards, X } from "lucide-react";

const links = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/banking", label: "Banking", icon: WalletCards },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/suppliers", label: "Suppliers", icon: Building2 },
  { href: "/audit", label: "Activity", icon: Activity },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null);
  const [invoiceCount, setInvoiceCount] = useState<number | null>(null);

  useEffect(() => {
    api<SetupStatus>("/setup/status")
      .then((status) => {
        if (!status.complete) {
          if (path !== "/setup") router.replace("/setup");
        } else if (!status.applied) {
          if (path !== "/setup") router.replace("/setup");
        } else if (!status.has_organization) {
          if (path !== "/setup/organization") router.replace("/setup/organization");
        } else if (!status.has_admin) {
          if (path !== "/setup/admin") router.replace("/setup/admin");
        } else {
          if (path.startsWith("/setup")) router.replace("/");
        }
      })
      .catch(() => {});
  }, [path, router]);

  useEffect(() => {
    if (path.startsWith("/setup") || path === "/auth") return;
    const fetchOrg = () => {
      api<Organization[]>("/organizations")
        .then((orgs) => {
          if (orgs && orgs.length > 0) setCurrentOrg(orgs[0]);
        })
        .catch(() => {});
    };
    fetchOrg();
    window.addEventListener("organizationUpdated", fetchOrg);

    api<Invoice[]>("/invoices")
      .then((items) => {
        setInvoiceCount(Array.isArray(items) ? items.length : 0);
      })
      .catch(() => {
        setInvoiceCount(null);
      });

    return () => {
      window.removeEventListener("organizationUpdated", fetchOrg);
    };
  }, [path]);


  if (path === "/setup" || path.startsWith("/setup/")) {
    return <main className="setup-shell">{children}</main>;
  }

  return (
    <div className="app-frame">
      <button className="mobile-menu" onClick={() => setOpen(!open)} aria-label={open ? "Close navigation" : "Open navigation"}>
        {open ? <X size={19} /> : <Menu size={19} />}
      </button>
      {open && <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <Link className="brand" href="/">
          <span className="brand-mark">O</span>
          <span>OpenInvoice</span>
        </Link>
        <button className="workspace">
          {currentOrg?.logo_key ? (
            <img
              src={`${API}/api/v1/organizations/${currentOrg.id}/logo`}
              alt={currentOrg.name}
              className="workspace-icon"
              style={{ objectFit: "contain", padding: 2, background: "#fff" }}
            />
          ) : (
            <span className="workspace-icon">
              {(currentOrg?.name?.[0] || "O").toUpperCase()}
            </span>
          )}
          <span className="workspace-name">
            {currentOrg?.name || "Workspace"}
            <small>Workspace</small>
          </span>
          <ChevronDown size={15} />
        </button>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`nav-link ${path === href || (path.startsWith(href + "/") && href !== "/") ? "active" : ""}`}
            >
              <Icon size={17} />
              {label}
              {label === "Invoices" && typeof invoiceCount === "number" && invoiceCount > 0 && (
                <span className="nav-count">{invoiceCount}</span>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Link href="/settings" className={`nav-link ${path === "/settings" ? "active" : ""}`}>
            <Settings size={17} />
            Settings
          </Link>
          <Link href="/auth" className={`nav-link ${path === "/auth" ? "active" : ""}`}>
            <LogIn size={17} />
            Sign in / switch account
          </Link>
          <div className="profile">
            <span className="avatar">OI</span>
            <span>
              OpenInvoice
              <small>Self-hosted workspace</small>
            </span>
          </div>
        </div>
      </aside>
      <main className="main-area">{children}</main>
    </div>
  );
}
