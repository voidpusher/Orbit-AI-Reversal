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
      <button className="brand button-reset" onClick={() => router.push("/")}>
        <OrbitLogo />
        orbit
      </button>
      <nav>
        {links.map(([Icon, name, path]) => (
          <button key={name} className={active === name ? "active" : ""} onClick={() => router.push(path)}>
            <Icon size={17} />
            {name}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button onClick={() => router.push("/settings")}>
          <Star size={16} /> Upgrade
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
