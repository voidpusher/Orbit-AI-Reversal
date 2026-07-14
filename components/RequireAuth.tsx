"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Gates a protected page: redirects to /login when there is no token or the
 * session is rejected. Renders a lightweight loader until identity is confirmed
 * so protected content never flashes for signed-out visitors.
 */
// Auth is disabled by default; set NEXT_PUBLIC_AUTH_DISABLED=false to enforce it.
const AUTH_DISABLED = process.env.NEXT_PUBLIC_AUTH_DISABLED !== "false";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [hasToken, setHasToken] = useState<boolean | null>(null);

  useEffect(() => {
    if (AUTH_DISABLED) return;
    const token = getToken();
    setHasToken(Boolean(token));
    if (!token) router.replace("/login");
  }, [router]);

  const { isLoading, error } = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: !AUTH_DISABLED && hasToken === true,
    retry: false,
    staleTime: 60_000,
  });

  // Dev mode: auth is disabled server-side, render straight through.
  if (AUTH_DISABLED) return <>{children}</>;

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) router.replace("/login");
  }, [error, router]);

  if (hasToken === null || (hasToken && isLoading)) {
    return (
      <div className="auth-loading">
        <Loader2 size={22} className="spin" />
      </div>
    );
  }
  if (!hasToken || error) return null;
  return <>{children}</>;
}
