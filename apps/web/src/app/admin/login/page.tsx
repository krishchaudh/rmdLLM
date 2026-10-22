"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Header } from "@/components/Header";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const r = useRouter();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Header />
      <main className="mx-auto max-w-sm px-5 py-24">
        <h1 className="font-serif text-3xl tracking-tight">Admin</h1>
        <form
          className="mt-8 space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setErr(null);
            try {
              const t = await api.login(u, p);
              setToken(t.access_token);
              r.push("/admin");
            } catch (e2) {
              setErr(e2 instanceof Error ? e2.message : "Login failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <input value={u} onChange={(e) => setU(e.target.value)} placeholder="Username" autoComplete="username" className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2.5 outline-none focus:border-stone-400" />
          <input value={p} onChange={(e) => setP(e.target.value)} placeholder="Password" type="password" autoComplete="current-password" className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2.5 outline-none focus:border-stone-400" />
          {err && <p className="text-sm text-red-700">{err}</p>}
          <button disabled={busy} className="w-full rounded-lg bg-stone-900 py-2.5 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50">
            Sign in
          </button>
        </form>
      </main>
    </>
  );
}
