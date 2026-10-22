"use client";

import { useEffect, useRef } from "react";
import { hasDevanagari } from "@/lib/api";

export function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  autoFocus,
  large,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  autoFocus?: boolean;
  large?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!busy && value.trim()) onSubmit();
      }}
      className="relative"
    >
      <textarea
        ref={ref}
        autoFocus={autoFocus}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!busy && value.trim()) onSubmit();
          }
        }}
        placeholder="Ask in English, हिन्दी, or Hinglish…"
        className={`w-full resize-none overflow-hidden rounded-2xl border border-stone-200 bg-white pr-14 shadow-sm outline-none transition placeholder:text-stone-400 focus:border-stone-400 focus:shadow-md ${
          large ? "px-5 py-4 text-[17px]" : "px-4 py-3 text-[15px]"
        } ${hasDevanagari(value) ? "devanagari" : ""}`}
      />
      <button
        type="submit"
        disabled={busy || !value.trim()}
        aria-label="Ask"
        className="absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-xl bg-stone-900 text-white transition hover:bg-orange-700 disabled:bg-stone-200 disabled:text-stone-400"
      >
        {busy ? (
          <span className="thinking flex gap-1">
            <span /> <span /> <span />
          </span>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        )}
      </button>
    </form>
  );
}
