"use client";

import { useEffect, useState } from "react";
import { useUser } from "@/lib/user";

type Mode = "signin" | "signup" | "reset";

export function AuthDialog() {
  const { authOpen, closeAuth, signIn, signUp, resetPassword } = useUser();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!authOpen) return;
    setMode("signin");
    setError(null);
    setNotice(null);
    setPassword("");
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeAuth();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [authOpen, closeAuth]);

  if (!authOpen) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "signin") {
        await signIn(email.trim(), password);
        closeAuth();
      } else if (mode === "signup") {
        const r = await signUp(email.trim(), password);
        if (r === "signed_in") closeAuth();
        else setNotice("Check your email for a confirmation link, then sign in.");
      } else {
        await resetPassword(email.trim());
        setNotice("If that email has an account, a reset link is on its way.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "signin" ? "Welcome back" : mode === "signup" ? "Create your account" : "Reset password";
  const cta = mode === "signin" ? "Sign in" : mode === "signup" ? "Create account" : "Send reset link";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/30 px-4 backdrop-blur-[2px]"
      onClick={closeAuth}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="fade-in w-full max-w-sm rounded-2xl border border-[var(--line)] bg-[var(--bg)] p-7 shadow-xl"
      >
        <h2 className="font-serif text-[26px] leading-tight tracking-tight text-stone-900">{title}</h2>
        <p className="mt-1.5 text-[13px] text-stone-500">
          {mode === "reset"
            ? "We'll email you a link to choose a new password."
            : "Save your conversations and pick them up on any device."}
        </p>

        <label className="mt-6 block text-xs font-medium text-stone-600">
          Email
          <input
            type="email"
            required
            autoFocus
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-[15px] text-stone-900 outline-none transition focus:border-stone-500"
          />
        </label>
        {mode !== "reset" && (
          <label className="mt-4 block text-xs font-medium text-stone-600">
            Password
            <input
              type="password"
              required
              minLength={6}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-[15px] text-stone-900 outline-none transition focus:border-stone-500"
            />
          </label>
        )}

        {error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>}
        {notice && <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[13px] text-emerald-800">{notice}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-full bg-stone-900 py-2.5 text-[15px] font-medium text-white transition hover:bg-stone-700 disabled:opacity-50"
        >
          {busy ? "…" : cta}
        </button>

        <div className="mt-5 flex items-center justify-between text-[13px] text-stone-500">
          {mode === "signin" ? (
            <>
              <button type="button" onClick={() => setMode("signup")} className="hover:text-stone-900">
                Create an account
              </button>
              <button type="button" onClick={() => setMode("reset")} className="hover:text-stone-900">
                Forgot password?
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setMode("signin")} className="hover:text-stone-900">
              ← Back to sign in
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
