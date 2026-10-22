"use client";

import { Fragment, useState } from "react";
import type { Citation } from "@/lib/api";
import { api, hasDevanagari } from "@/lib/api";

const CITE = /\[(\d{1,2})\]/g;

function renderWithCites(
  text: string,
  cites: Citation[],
  active: number | null,
  onCite: (n: number) => void,
) {
  const valid = new Set(cites.map((c) => c.n));
  return text.split(/\n{2,}/).map((para, pi) => {
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
      </p>
    );
  });
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
    <div className="fade-in">
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
