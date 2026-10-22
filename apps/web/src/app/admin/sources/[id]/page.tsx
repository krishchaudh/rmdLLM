"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, hasDevanagari, type Page } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function ReviewPage({ params }: { params: { id: string } }) {
  const r = useRouter();
  const [token, setTok] = useState<string | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState(true);
  const [pages, setPages] = useState<Page[]>([]);
  const [offset, setOffset] = useState(0);
  const [edit, setEdit] = useState<Page | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback((t: string, flagged: boolean, off: number) => {
    api.admin.pages(t, params.id, flagged ? true : null, off, 20).then(setPages).catch((e) => setMsg(e.message));
  }, [params.id]);

  useEffect(() => {
    const t = getToken();
    if (!t) {
      r.push("/admin/login");
      return;
    }
    setTok(t);
    load(t, onlyFlagged, offset);
  }, [r, load, onlyFlagged, offset]);

  if (!token) return null;

  const save = async () => {
    if (!edit) return;
    try {
      await api.admin.updatePage(token, params.id, edit.page_index, {
        text: edit.text,
        printed_page_number: edit.printed_page_number,
        needs_review: false,
      });
      setEdit(null);
      load(token, onlyFlagged, offset);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  };

  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-5 py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-serif text-3xl tracking-tight">Extraction review</h1>
          <label className="flex items-center gap-2 text-sm text-stone-600">
            <input type="checkbox" checked={onlyFlagged} onChange={(e) => { setOnlyFlagged(e.target.checked); setOffset(0); }} />
            Only flagged pages
          </label>
        </div>
        {msg && <p className="mt-3 text-sm text-red-700">{msg}</p>}
        <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
          <ul className="max-h-[70vh] divide-y divide-stone-200 overflow-auto rounded-xl border border-stone-200 bg-white scrollbar-thin">
            {pages.map((p) => (
              <li key={p.page_index}>
                <button onClick={() => setEdit({ ...p })} className={`w-full px-4 py-3 text-left text-sm hover:bg-stone-50 ${edit?.page_index === p.page_index ? "bg-orange-50" : ""}`}>
                  <div className="flex justify-between">
                    <span>PDF p. {p.page_index + 1}{p.printed_page_number ? ` · printed ${p.printed_page_number}` : ""}</span>
                    <span className="text-xs text-stone-400">{p.ocr_confidence != null ? `${Math.round(p.ocr_confidence * 100)}%` : p.extraction_method}</span>
                  </div>
                  {p.review_reason && <div className="text-xs text-amber-700">{p.review_reason}</div>}
                </button>
              </li>
            ))}
            {pages.length === 0 && <li className="px-4 py-6 text-sm text-stone-400">Nothing to show.</li>}
            <li className="flex justify-between px-4 py-2 text-xs text-stone-500">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))} className="disabled:opacity-30">← Prev</button>
              <button disabled={pages.length < 20} onClick={() => setOffset(offset + 20)} className="disabled:opacity-30">Next →</button>
            </li>
          </ul>
          {edit ? (
            <div className="grid gap-4 md:grid-cols-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={api.pageImageUrl(params.id, edit.page_index, 120)} alt="" className="rounded-xl border border-stone-200 bg-white" />
              <div className="flex flex-col gap-3">
                <input value={edit.printed_page_number ?? ""} onChange={(e) => setEdit({ ...edit, printed_page_number: e.target.value || null })} placeholder="Printed page number" className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm" />
                <textarea value={edit.text} onChange={(e) => setEdit({ ...edit, text: e.target.value })} className={`min-h-[50vh] flex-1 rounded-lg border border-stone-200 bg-white p-3 text-sm leading-relaxed ${hasDevanagari(edit.text) ? "devanagari" : ""}`} />
                <div className="flex gap-2">
                  <button onClick={save} className="rounded-lg bg-stone-900 px-4 py-2 text-sm text-white hover:bg-orange-700">Save &amp; mark reviewed</button>
                  <button onClick={() => setEdit(null)} className="rounded-lg border border-stone-200 px-4 py-2 text-sm">Cancel</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-xl border border-dashed border-stone-200 text-sm text-stone-400">Select a page to compare the scan with its text.</div>
          )}
        </div>
      </main>
    </>
  );
}
