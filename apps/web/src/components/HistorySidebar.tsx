"use client";

import { useState } from "react";
import { type ConversationSummary, hasDevanagari } from "@/lib/api";

type Props = {
  items: ConversationSummary[];
  loading: boolean;
  activeId: string | null;
  open: boolean;
  onClose: () => void;
  onNew: () => void;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

function bucket(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86_400_000;
  if (d.getTime() >= startToday) return "Today";
  if (d.getTime() >= startToday - day) return "Yesterday";
  if (d.getTime() >= startToday - 7 * day) return "Previous 7 days";
  if (d.getTime() >= startToday - 30 * day) return "Previous 30 days";
  return "Older";
}

export function HistorySidebar(p: Props) {
  const [editing, setEditing] = useState<{ id: string; title: string } | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);

  const groups: [string, ConversationSummary[]][] = [];
  for (const c of p.items) {
    const b = bucket(c.updated_at);
    const g = groups.find(([k]) => k === b);
    if (g) g[1].push(c);
    else groups.push([b, [c]]);
  }

  const commitRename = async () => {
    if (!editing) return;
    const t = editing.title.trim();
    const cur = p.items.find((c) => c.id === editing.id);
    setEditing(null);
    if (t && t !== (cur?.title ?? "")) await p.onRename(editing.id, t);
  };

  return (
    <>
      {p.open && (
        <button
          type="button"
          aria-label="Close history"
          onClick={p.onClose}
          className="fixed inset-0 z-30 bg-stone-900/20 lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[270px] flex-col border-r border-[var(--line)] bg-[#f4f1eb] transition-transform duration-200 lg:translate-x-0 ${
          p.open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Conversation history"
      >
        <div className="flex h-14 items-center justify-between px-4">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-stone-400">History</span>
          <button
            type="button"
            onClick={p.onClose}
            aria-label="Close history"
            className="rounded p-1 text-stone-400 hover:text-stone-700 lg:hidden"
          >
            ✕
          </button>
        </div>
        <div className="px-3">
          <button
            type="button"
            onClick={p.onNew}
            className="flex w-full items-center gap-2 rounded-lg border border-stone-300/80 bg-white/70 px-3 py-2 text-[13px] text-stone-700 transition hover:border-stone-400 hover:bg-white"
          >
            <span className="text-base leading-none">+</span> New conversation
          </button>
        </div>
        <nav className="mt-3 flex-1 overflow-y-auto px-3 pb-6">
          {p.loading && p.items.length === 0 && (
            <p className="px-2 py-3 text-[12px] text-stone-400">Loading…</p>
          )}
          {!p.loading && p.items.length === 0 && (
            <p className="px-2 py-3 text-[12px] leading-relaxed text-stone-400">
              Your conversations will appear here.
            </p>
          )}
          {groups.map(([label, items]) => (
            <div key={label} className="mt-3">
              <p className="px-2 pb-1 text-[11px] font-medium text-stone-400">{label}</p>
              <ul className="space-y-0.5">
                {items.map((c) => {
                  const active = c.id === p.activeId;
                  const title = c.title ?? "Untitled";
                  return (
                    <li key={c.id} className="group relative">
                      {editing?.id === c.id ? (
                        <input
                          autoFocus
                          value={editing.title}
                          onChange={(e) => setEditing({ id: c.id, title: e.target.value })}
                          onBlur={commitRename}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitRename();
                            if (e.key === "Escape") setEditing(null);
                          }}
                          className="w-full rounded-md border border-stone-400 bg-white px-2 py-1.5 text-[13px] text-stone-900 outline-none"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => p.onOpen(c.id)}
                          className={`w-full truncate rounded-md px-2 py-1.5 pr-8 text-left text-[13px] transition ${
                            active ? "bg-stone-900/[0.07] text-stone-900" : "text-stone-600 hover:bg-stone-900/[0.04] hover:text-stone-900"
                          } ${hasDevanagari(title) ? "devanagari !leading-normal" : ""}`}
                          title={title}
                        >
                          {title}
                        </button>
                      )}
                      {editing?.id !== c.id && (
                        <button
                          type="button"
                          aria-label="Conversation options"
                          onClick={(e) => {
                            e.stopPropagation();
                            setMenuFor(menuFor === c.id ? null : c.id);
                          }}
                          className={`absolute right-1 top-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-stone-400 transition hover:text-stone-800 ${
                            menuFor === c.id || active ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                          }`}
                        >
                          ···
                        </button>
                      )}
                      {menuFor === c.id && (
                        <div
                          className="fade-in absolute right-0 top-full z-10 mt-1 w-36 overflow-hidden rounded-lg border border-[var(--line)] bg-white text-[13px] shadow-md"
                          onMouseLeave={() => setMenuFor(null)}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              setMenuFor(null);
                              setEditing({ id: c.id, title });
                            }}
                            className="block w-full px-3 py-2 text-left text-stone-700 hover:bg-stone-50"
                          >
                            Rename
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              setMenuFor(null);
                              if (confirm("Delete this conversation?")) await p.onDelete(c.id);
                            }}
                            className="block w-full px-3 py-2 text-left text-red-700 hover:bg-red-50"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
