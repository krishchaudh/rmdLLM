"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Citation, hasDevanagari, type AskResponse, type StoredMessage } from "@/lib/api";
import { useUser } from "@/lib/user";
import { Answer, StreamingAnswer } from "./Answer";
import { Citations } from "./Citations";
import { Composer } from "./Composer";

type Stage = "retrieval" | "generation" | "verification";
type Turn = {
  id: string;
  question: string;
  response?: AskResponse;
  error?: string;
  stream?: { stage: Stage; text: string; citations: Citation[]; final?: boolean };
};


const SUGGESTIONS = [
  "Why doesn't material wealth provide lasting happiness?",
  "भक्ति बचपन से ही क्यों शुरू करनी चाहिए?",
  "Bhagavat prapti ke liye kya zaroori hai?",
  "What is prema rasa according to the book?",
];

const STORAGE_KEY = "rmd.chat.v1";

function turnsFromMessages(msgs: StoredMessage[], conversationId: string): Turn[] {
  const out: Turn[] = [];
  for (let i = 0; i < msgs.length; i++) {
    const m = msgs[i];
    if (m.role !== "user") continue;
    const a = msgs[i + 1]?.role === "assistant" ? msgs[i + 1] : null;
    out.push({
      id: m.id,
      question: m.content,
      response: a
        ? {
            conversation_id: conversationId,
            message_id: a.id,
            answer: a.content,
            abstained: a.abstained,
            citations: a.citations ?? [],
            followups: a.followups ?? [],
            language: "",
            latency_ms: {},
            verification_summary: {},
          }
        : undefined,
      error: a ? undefined : "No answer was saved for this question.",
    });
  }
  return out;
}

type ChatProps = {
  /** Set by the history sidebar: open a saved conversation (id) or start a new one (null). */
  openRequest?: { id: string | null; nonce: number };
  onConversationChange?: (id: string | null) => void;
  onHistoryChanged?: () => void;
};

export function Chat({ openRequest, onConversationChange, onHistoryChanged }: ChatProps) {
  const { user, getToken, enabled, openAuth } = useUser();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loadingConv, setLoadingConv] = useState(false);
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

  useEffect(() => {
    onConversationChange?.(conversationId);
  }, [conversationId, onConversationChange]);

  const reset = () => {
    setTurns([]);
    setConversationId(null);
    setActive(null);
    sessionStorage.removeItem(STORAGE_KEY);
  };

  // Sidebar requests: open a saved conversation or start fresh.
  const lastNonce = useRef(0);
  useEffect(() => {
    if (!openRequest || openRequest.nonce === lastNonce.current) return;
    lastNonce.current = openRequest.nonce;
    if (!openRequest.id) {
      reset();
      return;
    }
    const id = openRequest.id;
    let cancelled = false;
    (async () => {
      setLoadingConv(true);
      try {
        const t = await getToken();
        const conv = await api.conversation(id, t);
        if (cancelled) return;
        setTurns(turnsFromMessages(conv.messages, conv.id));
        setConversationId(conv.id);
        setActive(null);
        window.scrollTo({ top: 0 });
      } catch {
        if (!cancelled) reset();
      } finally {
        if (!cancelled) setLoadingConv(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRequest]);

  // Signing in mid-chat: adopt the guest conversation into the account.
  const claimedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!user || !conversationId || claimedFor.current === conversationId) return;
    claimedFor.current = conversationId;
    (async () => {
      const t = await getToken();
      if (!t) return;
      try {
        await api.me.claim(t, conversationId);
        onHistoryChanged?.();
      } catch {
        /* already owned by this account, or gone */
      }
    })();
  }, [user, conversationId, getToken, onHistoryChanged]);

  const ask = async (q: string) => {
    const id = crypto.randomUUID();
    setTurns((t) => [...t, { id, question: q }]);
    setDraft("");
    setBusy(true);
    try {
      // Accumulate deltas locally and flush at most once per animation frame; the typewriter
      // in StreamingAnswer then paces the reveal so bursts from the server don't show as jumps.
      let cur: NonNullable<Turn["stream"]> = { stage: "retrieval", text: "", citations: [] };
      let raf = 0;
      const flush = () => {
        raf = 0;
        const snap = cur;
        setTurns((t) => t.map((x) => (x.id === id ? { ...x, stream: snap } : x)));
      };
      const schedule = () => {
        if (!raf) raf = requestAnimationFrame(flush);
      };
      const token = await getToken();
      const r = await api.askStream(
        q,
        conversationId,
        (ev) => {
          if (ev.type === "status") cur = { ...cur, stage: ev.stage };
          else if (ev.type === "token") cur = { ...cur, text: cur.text + ev.text };
          else if (ev.type === "citations") cur = { ...cur, citations: ev.citations };
          else return;
          schedule();
        },
        token,
      );
      if (raf) cancelAnimationFrame(raf);
      setConversationId(r.conversation_id);
      if (token) {
        claimedFor.current = r.conversation_id;
        onHistoryChanged?.();
      }
      // Keep the typewriter until it has caught up, then hand off to the final Answer.
      const finalStream = { ...cur, text: r.answer, citations: r.citations, final: true };
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response: r, stream: finalStream } : x)));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  };

  if (loadingConv) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-2xl items-center justify-center px-5">
        <p className="fade-in text-sm text-stone-400">Opening conversation…</p>
      </main>
    );
  }

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
        {enabled && !user && (
          <p className="fade-in mt-10 text-center text-[12px] text-stone-400">
            <button type="button" onClick={openAuth} className="underline decoration-stone-300 underline-offset-2 hover:text-stone-700">
              Sign in
            </button>{" "}
            to save your conversations and come back to them.
          </p>
        )}
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
                  {t.response && !t.stream ? (
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
                    <StreamingAnswer
                      text={t.stream?.text ?? ""}
                      citations={t.stream?.citations ?? []}
                      stage={t.stream?.stage ?? "retrieval"}
                      final={!!t.stream?.final}
                      onSettled={() => setTurns((ts) => ts.map((x) => (x.id === t.id ? { ...x, stream: undefined } : x)))}
                    />
                  )}
                </div>
              </div>
              <div className="lg:pt-1">
                {t.response && !t.stream ? (
                  <Citations citations={t.response.citations} active={act} setActive={setAct} />
                ) : t.stream?.citations.length ? (
                  <div className="fade-in">
                    <Citations citations={t.stream.citations} active={null} setActive={() => {}} />
                  </div>
                ) : null}
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
