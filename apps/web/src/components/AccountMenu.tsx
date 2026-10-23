"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/user";

export function AccountMenu({ onHistoryCleared }: { onHistoryCleared?: () => void }) {
  const { enabled, ready, user, openAuth, signOut, getToken } = useUser();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!enabled) return null;
  if (!ready) return <span className="inline-block h-7 w-7 rounded-full bg-stone-200/70" aria-hidden />;

  if (!user) {
    return (
      <button
        type="button"
        onClick={openAuth}
        className="rounded-full border border-stone-300 px-3.5 py-1 text-[13px] text-stone-700 transition hover:border-stone-500 hover:text-stone-900"
      >
        Sign in
      </button>
    );
  }

  const initial = (user.email?.[0] ?? "?").toUpperCase();

  const clearHistory = async () => {
    if (!confirm("Delete all your saved conversations? This cannot be undone.")) return;
    setBusy("clear");
    try {
      const t = await getToken();
      if (t) await api.me.removeAll(t);
      onHistoryCleared?.();
      setOpen(false);
    } finally {
      setBusy(null);
    }
  };

  const deleteAccount = async () => {
    if (!confirm("Delete your account and all conversations? This cannot be undone.")) return;
    setBusy("delete");
    try {
      const t = await getToken();
      if (t) await api.me.deleteAccount(t);
      onHistoryCleared?.();
      await signOut();
      setOpen(false);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Account"
        aria-expanded={open}
        title={user.email ?? undefined}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-saffron-700 text-[12px] font-semibold text-white transition hover:bg-saffron-900"
      >
        {initial}
      </button>
      {open && (
        <div className="fade-in absolute right-0 mt-2 w-60 overflow-hidden rounded-xl border border-[var(--line)] bg-white shadow-lg">
          <div className="border-b border-[var(--line)] px-4 py-3">
            <p className="truncate text-[13px] text-stone-800">{user.email}</p>
            <p className="text-[11px] text-stone-400">Conversations are saved to this account</p>
          </div>
          <button
            type="button"
            disabled={!!busy}
            onClick={clearHistory}
            className="block w-full px-4 py-2.5 text-left text-[13px] text-stone-700 transition hover:bg-stone-50 disabled:opacity-50"
          >
            {busy === "clear" ? "Deleting…" : "Delete all conversations"}
          </button>
          <button
            type="button"
            disabled={!!busy}
            onClick={deleteAccount}
            className="block w-full px-4 py-2.5 text-left text-[13px] text-red-700 transition hover:bg-red-50 disabled:opacity-50"
          >
            {busy === "delete" ? "Deleting…" : "Delete account"}
          </button>
          <button
            type="button"
            onClick={async () => {
              await signOut();
              setOpen(false);
            }}
            className="block w-full border-t border-[var(--line)] px-4 py-2.5 text-left text-[13px] text-stone-700 transition hover:bg-stone-50"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
