"use client";

import { useEffect, useRef, useState } from "react";
import { api, hasDevanagari, type AskResponse } from "@/lib/api";
import { Answer } from "./Answer";
import { Citations } from "./Citations";
import { Composer } from "./Composer";

type Turn = { id: string; question: string; response?: AskResponse; error?: string };

const SUGGESTIONS = [
  "Why doesn't material wealth provide lasting happiness?",
  "भक्ति बचपन से ही क्यों शुरू करनी चाहिए?",
  "Bhagavat prapti ke liye kya zaroori hai?",
  "What is prema rasa according to the book?",
];

const STORAGE_KEY = "rmd.chat.v1";

export function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [active, setActive] = useState<{ turn: string; n: number } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [restored, setRestored] = useState(false);

  // Keep the conversation across navigation (e.g. opening a source page and coming back).
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as { turns: Turn[]; conversationId: string | null };
        setTurns(saved.turns.filter((t) => t.response || t.error));
        setConversationId(saved.conversationId);
      }
    } catch {
      /* ignore corrupt storage */
    }
    setRestored(true);
  }, []);
  useEffect(() => {
    if (!restored) return;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ turns, conversationId }));
  }, [turns, conversationId, restored]);

  useEffect(() => {
    if (busy) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  const reset = () => {
    setTurns([]);
    setConversationId(null);
    setActive(null);
    sessionStorage.removeItem(STORAGE_KEY);
  };

  const ask = async (q: string) => {
    const id = crypto.randomUUID();
    setTurns((t) => [...t, { id, question: q }]);
    setDraft("");
    setBusy(true);
    try {
      const r = await api.ask(q, conversationId);
      setConversationId(r.conversation_id);
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response: r } : x)));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  };

  if (turns.length === 0) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-2xl flex-col items-center justify-center px-5 pb-24">
        <h1 className="fade-in text-center font-serif text-[40px] leading-tight tracking-tight text-stone-900 sm:text-5xl">
          Ask the teachings.
        </h1>
        <p className="fade-in mt-4 max-w-md text-center text-[15px] leading-relaxed text-stone-500">
          Answers come only from the book <span className="font-serif italic">Prema Rasa Siddhānta</span> and
          Hindi lectures — every claim linked to the page or the exact moment in the video.
        </p>
        <div className="mt-10 w-full">
          <Composer value={draft} onChange={setDraft} onSubmit={() => ask(draft)} busy={busy} autoFocus large />
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className={`rounded-full border border-stone-200 bg-white/60 px-3.5 py-1.5 text-[13px] text-stone-600 transition hover:border-stone-400 hover:bg-white hover:text-stone-900 ${
                hasDevanagari(s) ? "devanagari" : ""
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-4 pb-36 pt-8 sm:px-6">
      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={reset}
          className="rounded-full border border-stone-200 px-3 py-1 text-xs text-stone-500 transition hover:border-stone-400 hover:text-stone-800"
        >
          New conversation
        </button>
      </div>
      <div className="space-y-14">
        {turns.map((t) => {
          const act = active?.turn === t.id ? active.n : null;
          const setAct = (n: number | null) => setActive(n === null ? null : { turn: t.id, n });
          return (
            <section key={t.id} className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div>
                <h2
                  className={`font-serif text-[26px] leading-snug tracking-tight text-stone-900 ${
                    hasDevanagari(t.question) ? "devanagari !font-devanagari" : ""
                  }`}
                >
                  {t.question}
                </h2>
                <div className="mt-5">
                  {t.response ? (
                    <Answer
                      messageId={t.response.message_id}
                      answer={t.response.answer}
                      abstained={t.response.abstained}
                      citations={t.response.citations}
                      followups={t.response.followups}
                      onFollowup={ask}
                      active={act}
                      setActive={setAct}
                    />
                  ) : t.error ? (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{t.error}</div>
                  ) : (
                    <div className="flex items-center gap-3 text-sm text-stone-400">
                      <span className="thinking flex gap-1">
                        <span /> <span /> <span />
                      </span>
                      Searching the sources
                    </div>
                  )}
                </div>
              </div>
              <div className="lg:pt-1">
                {t.response && <Citations citations={t.response.citations} active={act} setActive={setAct} />}
              </div>
            </section>
          );
        })}
        <div ref={bottomRef} />
      </div>
      <div className="fixed inset-x-0 bottom-0 z-10 bg-gradient-to-t from-[var(--bg)] via-[var(--bg)] to-transparent pb-5 pt-8">
        <div className="mx-auto max-w-2xl px-4">
          <Composer value={draft} onChange={setDraft} onSubmit={() => ask(draft)} busy={busy} />
          <p className="mt-2 text-center text-[11px] text-stone-400">
            Answers are grounded in cited sources and may decline when evidence is missing.
          </p>
        </div>
      </div>
    </main>
  );
}
