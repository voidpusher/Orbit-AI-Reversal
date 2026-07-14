"use client";

import { ArrowRight, Github, Loader2, Lock, Mail, TriangleAlert, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, API_BASE, ApiError } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";
import type { AuthResult } from "@/lib/types";

type Mode = "login" | "signup";

const OAUTH_ERRORS: Record<string, string> = {
  google_unconfigured: "Google sign-in isn’t configured on this server yet.",
  github_unconfigured: "GitHub sign-in isn’t configured on this server yet.",
  invalid_oauth_state: "That sign-in link expired. Please try again.",
  oauth_failed: "We couldn’t complete social sign-in. Please try again.",
  access_denied: "Sign-in was cancelled.",
};

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [oauthError, setOauthError] = useState<string | null>(null);

  // Handle the OAuth redirect back to /login#token=… or /login#error=…
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_AUTH_DISABLED !== "false") {
      router.replace("/dashboard");
      return;
    }
    const hash = window.location.hash.replace(/^#/, "");
    if (hash) {
      const params = new URLSearchParams(hash);
      const token = params.get("token");
      const error = params.get("error");
      history.replaceState(null, "", window.location.pathname);
      if (token) {
        setToken(token);
        router.replace("/dashboard");
        return;
      }
      if (error) setOauthError(OAUTH_ERRORS[error] ?? "Social sign-in failed. Please try again.");
    }
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  const startOAuth = (provider: "google" | "github") => {
    window.location.href = `${API_BASE}/api/v1/auth/oauth/${provider}/start`;
  };

  const mutation = useMutation({
    mutationFn: (): Promise<AuthResult> =>
      mode === "signup" ? api.signup(email, name, password) : api.login(email, password),
    onSuccess: (result) => {
      setToken(result.token);
      router.replace("/dashboard");
    },
  });

  const submit = () => {
    if (mutation.isPending) return;
    if (!email.trim() || !password || (mode === "signup" && !name.trim())) return;
    mutation.mutate();
  };

  const error =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? "Something went wrong. Please try again."
        : null;

  return (
    <main className="auth-page">
      <div className="auth-orb" />
      <div className="auth-card">
        <button className="brand button-reset" onClick={() => router.push("/")}>
          <span className="brand-mark"><span /></span>orbit
        </button>
        <div className="auth-copy">
          <h1>{mode === "signup" ? "Create your account" : "Welcome back"}</h1>
          <p>{mode === "signup" ? "Start understanding any software in minutes." : "Sign in to explore and understand any software."}</p>
        </div>

        <div className="auth-providers">
          <button className="provider-button" onClick={() => startOAuth("google")}>
            <GoogleMark /> Continue with Google
          </button>
          <button className="provider-button" onClick={() => startOAuth("github")}>
            <Github size={18} /> Continue with GitHub
          </button>
        </div>
        {oauthError && <div className="form-error"><TriangleAlert size={15} /> {oauthError}</div>}

        <div className="auth-divider"><span>or</span></div>

        {mode === "signup" && (
          <>
            <label className="field-label" htmlFor="name">Name</label>
            <div className="auth-email">
              <User size={17} />
              <input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" />
            </div>
          </>
        )}

        <label className="field-label" htmlFor="email">Email</label>
        <div className="auth-email">
          <Mail size={17} />
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>

        <label className="field-label" htmlFor="password">Password</label>
        <div className="auth-email">
          <Lock size={17} />
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
          />
        </div>

        {error && <div className="form-error"><TriangleAlert size={15} /> {error}</div>}

        <button className="button primary full" onClick={submit} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <><Loader2 size={16} className="spin" /> {mode === "signup" ? "Creating…" : "Signing in…"}</>
          ) : (
            <>{mode === "signup" ? "Create account" : "Sign in"} <ArrowRight size={16} /></>
          )}
        </button>

        <p className="auth-switch">
          {mode === "signup" ? "Already have an account?" : "New to Orbit?"}{" "}
          <button className="link-button" onClick={() => { setMode(mode === "signup" ? "login" : "signup"); mutation.reset(); }}>
            {mode === "signup" ? "Sign in" : "Create an account"}
          </button>
        </p>

        <p className="auth-fine">
          By continuing you agree to Orbit&rsquo;s exploration policy. Orbit analyzes public surfaces only.
        </p>
      </div>
    </main>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z" />
    </svg>
  );
}
