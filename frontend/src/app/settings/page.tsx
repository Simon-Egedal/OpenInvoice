"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { PersonalSettings } from "@/components/personal-settings";

export default function Settings() {
  const [sessionMessage, setSessionMessage] = useState("");

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <header className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-description">Manage your name, password, and session.</p>
        </div>
      </header>

      <PersonalSettings />

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


    </div>
  );
}
