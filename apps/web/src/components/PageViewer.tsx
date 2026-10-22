"use client";

import { useEffect, useState } from "react";
import { api, hasDevanagari, type Page, type Source } from "@/lib/api";

export function PageViewer({ sourceId, initialPage }: { sourceId: string; initialPage: number }) {
  const [source, setSource] = useState<Source | null>(null);
  const [pageNo, setPageNo] = useState(initialPage); // 1-based
  const [page, setPage] = useState<Page | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pageErr, setPageErr] = useState<string | null>(null);
  const [imgErr, setImgErr] = useState(false);

  useEffect(() => {
    api.source(sourceId).then(setSource).catch((e) => setErr(e.message));
  }, [sourceId]);
  const total = source?.book?.page_count ?? 0;
  useEffect(() => {
    // Clamp out-of-range page numbers (e.g. ?page=9999) once we know the page count.
    if (total > 0 && pageNo > total) setPageNo(total);
    else if (pageNo < 1) setPageNo(1);
  }, [total, pageNo]);
  useEffect(() => {
    setPage(null);
    setPageErr(null);
    setImgErr(false);
    api
      .page(sourceId, pageNo - 1)
      .then(setPage)
      .catch(() => setPageErr(`Page ${pageNo} is not available for this source.`));
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      u.searchParams.set("page", String(pageNo));
      window.history.replaceState(null, "", u.toString());
    }
  }, [sourceId, pageNo]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-stone-400">Book</div>
          <h1 className="font-serif text-3xl tracking-tight">{source?.title ?? "…"}</h1>
          {source?.book?.author && <div className="text-sm text-stone-500">{source.book.author}</div>}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <button onClick={() => setPageNo((p) => Math.max(1, p - 1))} className="rounded-md border border-stone-200 bg-white px-3 py-1.5 hover:border-stone-400">
            ←
          </button>
          <span className="tabular-nums text-stone-600">
            PDF page {pageNo}
            {total ? ` / ${total}` : ""}
            {page?.printed_page_number ? ` · printed p. ${page.printed_page_number}` : ""}
          </span>
          <button onClick={() => setPageNo((p) => (total ? Math.min(total, p + 1) : p + 1))} className="rounded-md border border-stone-200 bg-white px-3 py-1.5 hover:border-stone-400">
            →
          </button>
          <a href={`${api.pdfUrl(sourceId)}#page=${pageNo}`} target="_blank" rel="noreferrer" className="ml-2 text-stone-600 underline-offset-4 hover:underline">
            Open PDF
          </a>
        </div>
      </div>
      {err && <p className="mt-6 text-sm text-red-700">{err}</p>}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded-xl border border-stone-200 bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {imgErr || pageErr ? (
            <div className="flex aspect-[3/4] items-center justify-center p-6 text-center text-sm text-stone-400">
              {pageErr ?? "Scan image could not be loaded."}
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={pageNo}
              src={api.pageImageUrl(sourceId, pageNo - 1, 130)}
              alt={`Page ${pageNo}`}
              className="w-full"
              onError={() => setImgErr(true)}
            />
          )}
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-6">
          <div className="mb-3 flex items-center justify-between text-xs text-stone-400">
            <span>Extracted text</span>
            {page && (
              <span>
                {page.extraction_method}
                {page.ocr_confidence != null ? ` · agreement ${(page.ocr_confidence * 100).toFixed(0)}%` : ""}
                {page.needs_review ? " · flagged for review" : ""}
              </span>
            )}
          </div>
          <pre
            className={`whitespace-pre-wrap text-[14.5px] leading-relaxed text-stone-800 ${
              page && hasDevanagari(page.text) ? "devanagari" : "font-serif"
            }`}
          >
            {page ? page.text || "(no text on this page)" : (pageErr ?? "Loading…")}
          </pre>
        </div>
      </div>
    </main>
  );
}
