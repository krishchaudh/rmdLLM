"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ConversationSummary } from "@/lib/api";
import { useUser } from "@/lib/user";
import { AccountMenu } from "./AccountMenu";
import { Chat } from "./Chat";
import { Header } from "./Header";
import { HistorySidebar } from "./HistorySidebar";

export function ChatShell() {
  const { user, getToken, enabled } = useUser();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [openReq, setOpenReq] = useState<{ id: string | null; nonce: number }>({ id: null, nonce: 0 });
  const [drawer, setDrawer] = useState(false);
  const prevUser = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    const t = await getToken();
    if (!t) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      setItems(await api.me.conversations(t));
    } catch {
      /* sidebar is best-effort */
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    refresh();
  }, [user?.id, refresh]);

  // Signing out: the open conversation now belongs to an account → start fresh.
  useEffect(() => {
    if (prevUser.current && !user) setOpenReq((r) => ({ id: null, nonce: r.nonce + 1 }));
    prevUser.current = user?.id ?? null;
  }, [user]);

  const withToken = async (fn: (t: string) => Promise<unknown>) => {
    const t = await getToken();
    if (t) await fn(t);
    await refresh();
  };

  const signedIn = enabled && !!user;

  return (
    <div className={signedIn ? "lg:pl-[270px]" : ""}>
      <Header
        left={
          signedIn ? (
            <button
              type="button"
              aria-label="Open history"
              onClick={() => setDrawer(true)}
              className="mr-3 rounded p-1 text-stone-500 hover:text-stone-900 lg:hidden"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
              </svg>
            </button>
          ) : undefined
        }
        right={
          <AccountMenu
            onHistoryCleared={() => {
              setItems([]);
              setActiveId(null);
              setOpenReq((r) => ({ id: null, nonce: r.nonce + 1 }));
            }}
          />
        }
      />
      {signedIn && (
        <HistorySidebar
          items={items}
          loading={loading}
          activeId={activeId}
          open={drawer}
          onClose={() => setDrawer(false)}
          onNew={() => {
            setDrawer(false);
            setOpenReq((r) => ({ id: null, nonce: r.nonce + 1 }));
          }}
          onOpen={(id) => {
            setDrawer(false);
            setOpenReq((r) => ({ id, nonce: r.nonce + 1 }));
          }}
          onRename={(id, title) => withToken((t) => api.me.rename(t, id, title))}
          onDelete={async (id) => {
            await withToken((t) => api.me.remove(t, id));
            if (id === activeId) setOpenReq((r) => ({ id: null, nonce: r.nonce + 1 }));
          }}
        />
      )}
      <Chat openRequest={openReq} onConversationChange={setActiveId} onHistoryChanged={refresh} />
    </div>
  );
}
