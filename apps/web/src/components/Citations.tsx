"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import type { Citation } from "@/lib/api";
import { api, fmtTime, hasDevanagari } from "@/lib/api";

function CitationCard({ c, active, onSelect }: { c: Citation; active: boolean; onSelect: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);
  const isLecture = c.kind === "lecture";
  return (
    <div
      ref={ref}
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border bg-white p-4 transition ${
        active ? "border-orange-700/60 shadow-[0_0_0_3px_rgba(194,65,12,0.08)]" : "border-stone-200 hover:border-stone-300"
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-stone-500">
          <span className={`cite ${active ? "active" : ""} !align-baseline`}>{c.n}</span>
          <span className="uppercase tracking-wide">{isLecture ? "Lecture" : "Book"}</span>
        </div>
        {isLecture && c.url ? (
          <a
            href={c.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md bg-stone-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-orange-700"
            onClick={(e) => e.stopPropagation()}
          >
            ▶ {fmtTime(c.start_seconds ?? 0)}
          </a>
        ) : (
          <Link
            href={`/sources/${c.source_id}?page=${(c.page_index ?? 0) + 1}`}
            className="inline-flex items-center gap-1.5 rounded-md bg-stone-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-orange-700"
            onClick={(e) => e.stopPropagation()}
          >
            Open page {(c.page_index ?? 0) + 1}
          </Link>
        )}
      </div>
      <div className="font-serif text-[15px] leading-snug text-stone-900">{c.title}</div>
      <div className="mt-0.5 text-xs text-stone-500">
        {isLecture
          ? `${fmtTime(c.start_seconds ?? 0)} – ${fmtTime(c.end_seconds ?? 0)} · YouTube`
          : c.where}
      </div>
      <blockquote
        className={`mt-3 border-l-2 border-stone-200 pl-3 text-[13.5px] leading-relaxed text-stone-600 ${
          active ? "" : "line-clamp-4"
        } ${hasDevanagari(c.text) ? "devanagari" : "font-serif"}`}
      >
        {c.text}
      </blockquote>
      {!isLecture && active && c.page_index !== undefined && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={api.pageImageUrl(c.source_id, c.page_index, 80)}
          alt={`Page ${c.page_index + 1}`}
          className="mt-3 w-full rounded-md border border-stone-200"
          loading="lazy"
        />
      )}
    </div>
  );
}

export function Citations({
  citations,
  active,
  setActive,
}: {
  citations: Citation[];
  active: number | null;
  setActive: (n: number | null) => void;
}) {
  if (!citations.length) return null;
  return (
    <aside className="space-y-3">
      <div className="px-1 text-xs font-medium uppercase tracking-wider text-stone-400">
        Sources · {citations.length}
      </div>
      {citations.map((c) => (
        <CitationCard key={c.chunk_id} c={c} active={active === c.n} onSelect={() => setActive(active === c.n ? null : c.n)} />
      ))}
    </aside>
  );
}
