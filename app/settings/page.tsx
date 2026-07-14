"use client";

import { Check, CreditCard, Gauge, KeyRound, LogOut, Mail, Shield, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, API_BASE } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { AppSidebar } from "@/components/AppSidebar";
import { RequireAuth } from "@/components/RequireAuth";

const PLANS = [
  { name: "Free", key: "free", price: "$0", features: ["25 analyses / month", "Evidence-backed reports", "Markdown export"] },
  { name: "Pro", key: "pro", price: "$29", features: ["Unlimited analyses", "Deep crawl", "JSON + Markdown export", "Compare mode"] },
  { name: "Enterprise", key: "enterprise", price: "Custom", features: ["SSO & RBAC", "Audit logs", "Private deployment", "Priority support"] },
];

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsInner />
    </RequireAuth>
  );
}

function SettingsInner() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      clearToken();
      qc.clear();
      router.replace("/login");
    }
  };

  const used = me?.usage.analyses_this_month ?? 0;
  const limit = me?.usage.monthly_limit ?? null;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  return (
    <main className="dashboard">
      <AppSidebar active="Settings" />
      <section className="dashboard-main">
        <header className="dash-header">
          <div><span className="eyebrow">Account</span><h1>Settings.</h1></div>
          <button className="button ghost" onClick={logout}><LogOut size={15} /> Sign out</button>
        </header>

        <div className="settings-stack">
          <section className="settings-card">
            <div className="settings-card-head"><User size={18} /><h2>Profile</h2></div>
            <div className="settings-rows">
              <Field icon={<User size={16} />} label="Name" value={me?.name ?? "—"} />
              <Field icon={<Mail size={16} />} label="Email" value={me?.email ?? "—"} />
              <Field icon={<Shield size={16} />} label="Organization" value={me ? `${me.organization} · ${me.role}` : "—"} />
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-head"><Gauge size={18} /><h2>Usage this month</h2></div>
            <div className="usage-row">
              <div className="usage-meta">
                <b>{used}{limit ? ` / ${limit}` : ""} analyses</b>
                <small>{limit ? `${limit - used} remaining on your ${me?.plan} plan` : "Unlimited on your plan"}</small>
              </div>
              {limit ? (
                <div className="usage-track"><i style={{ width: `${pct}%` }} className={pct >= 90 ? "hot" : ""} /></div>
              ) : (
                <span className="pill">Unlimited</span>
              )}
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-head"><CreditCard size={18} /><h2>Plan &amp; billing</h2></div>
            <div className="pricing-grid">
              {PLANS.map((plan) => {
                const current = me?.plan === plan.key;
                return (
                  <article className={`pricing-plan ${current ? "current" : ""}`} key={plan.name}>
                    {current && <span className="pricing-flag">Current plan</span>}
                    <b>{plan.name}</b>
                    <strong>{plan.price}<small>{plan.price !== "Custom" ? "/mo" : ""}</small></strong>
                    <ul>{plan.features.map((f) => <li key={f}><Check size={14} /> {f}</li>)}</ul>
                    <button className={`button ${current ? "ghost" : "primary"} full`} disabled={current}>
                      {current ? "Active" : plan.name === "Enterprise" ? "Contact sales" : "Upgrade"}
                    </button>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-head"><KeyRound size={18} /><h2>API access</h2></div>
            <p className="settings-note">Your dashboard is powered by the Orbit API. Programmatic API keys are on the roadmap.</p>
            <div className="code-row"><code>{API_BASE}/api/v1</code><span className="pill">v1</span></div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="settings-field">
      <span className="settings-field-label">{icon} {label}</span>
      <span className="settings-field-value">{value}</span>
    </div>
  );
}
