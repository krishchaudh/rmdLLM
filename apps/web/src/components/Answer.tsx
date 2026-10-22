"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import type { Citation } from "@/lib/api";
import { api, hasDevanagari } from "@/lib/api";

const CITE = /\[(\d{1,2})\]/g;

export function renderWithCites(
  text: string,
  cites: Citation[],
  active: number | null,
  onCite: (n: number) => void,
  tail?: React.ReactNode,
) {
  const valid = new Set(cites.map((c) => c.n));
  const paras = text.split(/\n{2,}/);
  return paras.map((para, pi) => {
    const parts: React.ReactNode[] = [];
    let last = 0;
    for (const m of Array.from(para.matchAll(CITE))) {
      const n = Number(m[1]);
      parts.push(para.slice(last, m.index));
      if (valid.has(n)) {
        parts.push(
          <button
            key={`${pi}-${m.index}`}
            className={`cite ${active === n ? "active" : ""}`}
            onClick={() => onCite(n)}
            aria-label={`Citation ${n}`}
          >
            {n}
          </button>,
        );
      }
      last = (m.index ?? 0) + m[0].length;
    }
    parts.push(para.slice(last));
    return (
      <p key={pi} className={hasDevanagari(para) ? "devanagari" : undefined}>
        {parts.map((p, i) => <Fragment key={i}>{p}</Fragment>)}
        {pi === paras.length - 1 ? tail : null}
      </p>
    );
  });
}

/** Reveal `target` at a steady pace (speeding up when it falls behind), like ChatGPT's typewriter.
 *  Returns the text to show; calls `onSettled` once everything is shown and `final` is true. */
export function useSmoothText(target: string, final: boolean, onSettled?: () => void) {
  const [shown, setShown] = useState(0);
  const shownRef = useRef(0);
  const settledRef = useRef(false);
  const cb = useRef(onSettled);
  cb.current = onSettled;
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    const tick = (now: number) => {
      const dt = Math.min(64, now - last);
      last = now;
      const backlog = target.length - shownRef.current;
      if (backlog > 0) {
        // base ~70 chars/s, plus a catch-up term so we never lag more than ~1s behind.
        const rate = final ? 0.35 + backlog / 400 : 0.07 + backlog / 1400; // chars per ms
        acc += rate * dt;
        const step = Math.min(backlog, Math.floor(acc));
        if (step > 0) {
          acc -= step;
          shownRef.current += step;
          setShown(shownRef.current);
        }
      } else if (final && !settledRef.current) {
        settledRef.current = true;
        cb.current?.();
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, final]);
  return target.slice(0, shown).replace(/\[\d{0,2}$/, "");
}

export function StreamingAnswer({
  text,
  citations,
  stage,
  final,
  onSettled,
}: {
  text: string;
  citations: Citation[];
  stage: "retrieval" | "generation" | "verification";
  final: boolean;
  onSettled: () => void;
}) {
  const shown = useSmoothText(text, final, onSettled);
  // Keep the caret visible above the composer while writing. Scrolling up pauses following;
  // scrolling back down to where the caret is visible resumes it.
  const caretRef = useRef<HTMLSpanElement>(null);
  const follow = useRef(true);
  useEffect(() => {
    let touchY = 0;
    const caretVisible = () => {
      const r = caretRef.current?.getBoundingClientRect();
      return !!r && r.top >= 0 && r.bottom <= window.innerHeight;
    };
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) follow.current = false;
      else if (caretVisible()) follow.current = true;
    };
    const onTouchStart = (e: TouchEvent) => {
      touchY = e.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY ?? 0;
      if (y > touchY) follow.current = false;
      else if (caretVisible()) follow.current = true;
      touchY = y;
    };
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
    };
  }, []);
  useEffect(() => {
    const r = caretRef.current?.getBoundingClientRect();
    if (!follow.current || !r) return;
    const limit = window.innerHeight - 190; // space for the fixed composer
    if (r.bottom > limit) window.scrollBy(0, r.bottom - limit);
  }, [shown.length]);
  const label =
    stage === "retrieval"
      ? "Searching the sources"
      : stage === "generation" || shown.length < text.length
        ? "Writing"
        : "Verifying every claim against the sources";
  return (
    <div>
      {shown && (
        <div className="prose-answer text-[17px] leading-[1.75] text-stone-800">
          {renderWithCites(shown, citations, null, () => {}, <span ref={caretRef} className="caret" aria-hidden />)}
        </div>
      )}
      <div className={`flex items-center gap-3 text-sm text-stone-400 ${shown ? "mt-4" : ""}`}>
        <span className="thinking flex gap-1">
          <span /> <span /> <span />
        </span>
        {label}
      </div>
    </div>
  );
}

export function Answer({
  messageId,
  answer,
  abstained,
  citations,
  followups,
  onFollowup,
  active,
  setActive,
}: {
  messageId: string;
  answer: string;
  abstained: boolean;
  citations: Citation[];
  followups: string[];
  onFollowup: (q: string) => void;
  active: number | null;
  setActive: (n: number | null) => void;
}) {
  const [voted, setVoted] = useState<1 | -1 | null>(null);
  const vote = async (r: 1 | -1) => {
    setVoted(r);
    try {
      await api.feedback(messageId, r);
    } catch {
      /* non-blocking */
    }
  };
  return (
    <div>
      {abstained && (
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-1 text-xs text-stone-500">
          <span className="h-1.5 w-1.5 rounded-full bg-stone-400" />
          Not enough evidence in the sources
        </div>
      )}
      <div className="prose-answer text-[17px] leading-[1.75] text-stone-800">
        {renderWithCites(answer, citations, active, (n) => setActive(active === n ? null : n))}
      </div>
      {followups.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          {followups.map((q) => (
            <button
              key={q}
              onClick={() => onFollowup(q)}
              className={`rounded-full border border-stone-200 bg-white px-3.5 py-1.5 text-left text-[13px] text-stone-600 transition hover:border-stone-400 hover:text-stone-900 ${
                hasDevanagari(q) ? "devanagari" : ""
              }`}
            >
              {q}
            </button>
          ))}
        </div>
      )}
      <div className="mt-5 flex items-center gap-1 text-stone-400">
        <button
          onClick={() => vote(1)}
          aria-label="Helpful"
          className={`rounded-md p-1.5 transition hover:bg-stone-100 hover:text-stone-700 ${voted === 1 ? "text-orange-700" : ""}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
          </svg>
        </button>
        <button
          onClick={() => vote(-1)}
          aria-label="Not helpful"
          className={`rounded-md p-1.5 transition hover:bg-stone-100 hover:text-stone-700 ${voted === -1 ? "text-orange-700" : ""}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="rotate-180">
            <path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
          </svg>
        </button>
        {voted && <span className="ml-1 text-xs">Thanks</span>}
      </div>
    </div>
  );
}
