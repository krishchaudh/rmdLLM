"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/Header";
import { supabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    // The recovery link signs the user in via the URL hash; wait for that session.
    supabase.auth.getSession().then(({ data }) => setReady(!!data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((evt, session) => {
      if (evt === "PASSWORD_RECOVERY" || session) setReady(true);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const { error } = await supabase!.auth.updateUser({ password });
    if (error) setError(error.message);
    else {
      setDone(true);
      setTimeout(() => router.push("/"), 1200);
    }
  };

  return (
    <>
      <Header />
      <main className="mx-auto max-w-sm px-5 py-16">
        <h1 className="font-serif text-[30px] tracking-tight text-stone-900">Choose a new password</h1>
        {!supabase ? (
          <p className="mt-4 text-sm text-stone-500">Accounts are not enabled.</p>
        ) : !ready ? (
          <p className="mt-4 text-sm text-stone-500">
            Open this page from the link in your reset email. Waiting for that link…
          </p>
        ) : done ? (
          <p className="mt-4 text-sm text-emerald-800">Password updated — taking you back.</p>
        ) : (
          <form onSubmit={submit} className="mt-6">
            <input
              type="password"
              required
              minLength={6}
              autoFocus
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="New password"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-[15px] outline-none focus:border-stone-500"
            />
            {error && <p className="mt-3 text-[13px] text-red-700">{error}</p>}
            <button
              type="submit"
              className="mt-4 w-full rounded-full bg-stone-900 py-2.5 text-[15px] font-medium text-white hover:bg-stone-700"
            >
              Save password
            </button>
          </form>
        )}
      </main>
    </>
  );
}
