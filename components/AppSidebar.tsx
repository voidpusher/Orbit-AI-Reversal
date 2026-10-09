"use client";

import { ChevronRight, FileText, GitCompareArrows, LayoutDashboard, Plus, Settings, Star } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { OrbitLogo } from "@/components/OrbitLogo";

const links: [React.ComponentType<{ size?: number }>, string, string][] = [
  [LayoutDashboard, "Dashboard", "/dashboard"],
  [Plus, "New analysis", "/analyze"],
  [FileText, "Reports", "/reports"],
  [GitCompareArrows, "Compare", "/compare"],
  [Settings, "Settings", "/settings"],
];

export function AppSidebar({ active }: { active: string }) {
  const router = useRouter();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: Infinity });
  const initials = (me?.name ?? "Orbit User")
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand-row">
        <button className="brand button-reset" onClick={() => router.push("/")} aria-label="Orbit home">
          <OrbitLogo />
          <span>orbit</span>
        </button>
      </div>
      <nav>
        {links.map(([Icon, name, path]) => (
          <button
            key={name}
            className={`${active === name ? "active" : ""}${name === "New analysis" ? " nav-primary" : ""}`}
            onClick={() => router.push(path)}
            aria-current={active === name ? "page" : undefined}
          >
            <Icon size={17} />
            <span>{name}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button className="upgrade-card" onClick={() => router.push("/settings")}>
          <span><Star size={15} /> Orbit Pro</span>
        </button>
        <button className="sidebar-user button-reset" onClick={() => router.push("/settings")}>
          <span>{initials}</span>
          <div>
            <b>{me?.name ?? "Orbit User"}</b>
            <small>{me?.plan ? `${me.plan[0].toUpperCase()}${me.plan.slice(1)} plan` : "Loading…"}</small>
          </div>
          <ChevronRight size={15} />
        </button>
      </div>
    </aside>
  );
}
