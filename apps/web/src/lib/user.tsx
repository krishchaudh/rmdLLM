"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export type User = { id: string; email: string | null };

type Ctx = {
  enabled: boolean;
  ready: boolean;
  user: User | null;
  /** Fresh access token (auto-refreshed) or null for guests. */
  getToken: () => Promise<string | null>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<"signed_in" | "confirm_email">;
  resetPassword: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  authOpen: boolean;
  openAuth: () => void;
  closeAuth: () => void;
};

const UserContext = createContext<Ctx | null>(null);

function toUser(s: Session | null): User | null {
  return s?.user ? { id: s.user.id, email: s.user.email ?? null } : null;
}

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!supabase);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setUser(toUser(data.session));
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_evt, session) => {
      setUser(toUser(session));
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const getToken = useCallback(async () => {
    if (!supabase) return null;
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      enabled: !!supabase,
      ready,
      user,
      getToken,
      signIn: async (email, password) => {
        if (!supabase) throw new Error("Accounts are not enabled");
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error(friendly(error.message));
      },
      signUp: async (email, password) => {
        if (!supabase) throw new Error("Accounts are not enabled");
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw new Error(friendly(error.message));
        return data.session ? "signed_in" : "confirm_email";
      },
      resetPassword: async (email) => {
        if (!supabase) throw new Error("Accounts are not enabled");
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset`,
        });
        if (error) throw new Error(friendly(error.message));
      },
      signOut: async () => {
        await supabase?.auth.signOut();
      },
      authOpen,
      openAuth: () => setAuthOpen(true),
      closeAuth: () => setAuthOpen(false),
    }),
    [ready, user, getToken, authOpen],
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

function friendly(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login")) return "Wrong email or password.";
  if (m.includes("already registered")) return "An account with this email already exists — sign in instead.";
  if (m.includes("password should be")) return "Password must be at least 6 characters.";
  if (m.includes("rate limit")) return "Too many attempts — please wait a minute.";
  return msg;
}

export function useUser(): Ctx {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside <UserProvider>");
  return ctx;
}
