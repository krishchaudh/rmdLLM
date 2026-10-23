"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, ApiError, fmtTime, type Job, type Source } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";

export default function AdminPage() {
  const r = useRouter();
  const [token, setTok] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [tab, setTab] = useState<"lecture" | "book">("lecture");
  const [lec, setLec] = useState({ url: "", title: "", transcript: "" });
  const [fetching, setFetching] = useState(false);
  const [book, setBook] = useState<{ title: string; author: string; file: File | null }>({ title: "", author: "", file: null });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (t: string) => {
    try {
      const [s, j, st] = await Promise.all([api.sources(), api.admin.jobs(t), api.admin.stats(t)]);
      setSources(s);
      setJobs(j);
      setStats(st);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setToken(null);
        r.push("/admin/login");
      } else setMsg(e instanceof Error ? e.message : "error");
    }
  }, [r]);

  useEffect(() => {
    const t = getToken();
    if (!t) {
      r.push("/admin/login");
      return;
    }
    setTok(t);
    refresh(t);
    const iv = setInterval(() => refresh(t), 8000);
    return () => clearInterval(iv);
  }, [r, refresh]);

  if (!token) return null;

  const fetchTranscript = async () => {
    if (!token) return;
    setFetching(true);
    setMsg(null);
    try {
      const r = await api.admin.fetchTranscript(token, lec.url);
      setLec((l) => ({ ...l, transcript: r.transcript }));
      setMsg(`Fetched ${r.segments} caption lines (${r.language}). Review, then click Ingest.`);
    } catch (e2) {
      setMsg(e2 instanceof Error ? e2.message : "Could not fetch transcript — paste it manually.");
    } finally {
      setFetching(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (tab === "lecture") {
        await api.admin.addLecture(token, { url: lec.url, transcript: lec.transcript, title: lec.title || undefined });
        setLec({ url: "", title: "", transcript: "" });
      } else {
        if (!book.file) throw new Error("Choose a PDF");
        const fd = new FormData();
        fd.append("file", book.file);
        fd.append("title", book.title);
        if (book.author) fd.append("author", book.author);
        await api.admin.uploadBook(token, fd);
        setBook({ title: "", author: "", file: null });
      }
      setMsg("Ingestion started — status updates below (about a minute for a lecture, ~1 hr for a book).");
      refresh(token);
    } catch (e2) {
      setMsg(e2 instanceof Error ? e2.message : "error");
    } finally {
      setBusy(false);
    }
  };

  const fb = stats?.feedback as { up: number; down: number } | undefined;
  return (
    <>
      <Header
        right={
          <button
            onClick={() => {
              setToken(null);
              r.push("/");
            }}
            className="hover:text-stone-900"
          >
            Sign out
          </button>
        }
      />
      <main className="mx-auto max-w-5xl px-5 py-10">
        <h1 className="font-serif text-3xl tracking-tight">Admin</h1>
        {stats && (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Sources", String(stats.sources)],
              ["Answers", String(stats.answers)],
              ["Abstained", String(stats.abstained)],
              ["Est. cost", `$${Number(stats.estimated_cost_usd).toFixed(3)}`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-stone-200 bg-white p-4">
                <div className="text-xs uppercase tracking-wider text-stone-400">{k}</div>
                <div className="mt-1 font-serif text-2xl">{v}</div>
              </div>
            ))}
            {fb && <div className="col-span-2 text-xs text-stone-500 sm:col-span-4">Feedback: {fb.up} helpful · {fb.down} not helpful</div>}
          </div>
        )}

        <section className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-xl border border-stone-200 bg-white p-5">
            <div className="flex gap-4 text-sm">
              {(["lecture", "book"] as const).map((t) => (
                <button key={t} onClick={() => setTab(t)} className={`border-b-2 pb-1 capitalize ${tab === t ? "border-stone-900 text-stone-900" : "border-transparent text-stone-400"}`}>
                  Add {t}
                </button>
              ))}
            </div>
            <form onSubmit={submit} className="mt-4 space-y-3">
              {tab === "lecture" ? (
                <>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <input required value={lec.url} onChange={(e) => setLec({ ...lec, url: e.target.value })} placeholder="YouTube URL" className="min-w-0 flex-1 rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-stone-400" />
                    <button type="button" disabled={fetching || !lec.url} onClick={fetchTranscript} className="shrink-0 rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:border-stone-500 disabled:opacity-50">
                      {fetching ? "Fetching…" : "Fetch transcript"}
                    </button>
                  </div>
                  <input value={lec.title} onChange={(e) => setLec({ ...lec, title: e.target.value })} placeholder="Title (optional)" className="w-full rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-stone-400" />
                  <textarea required value={lec.transcript} onChange={(e) => setLec({ ...lec, transcript: e.target.value })} rows={8} placeholder={"Paste the transcript (YouTube: “…more → Show transcript”, select all, copy):\n0:00\nदो प्रकार के कर्म होते हैं।\n0:05\n…"} className="devanagari w-full rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-stone-400" />
                  <p className="text-xs text-stone-500">Accepted: YouTube transcript panel (either layout), “M:SS text” lines, SRT, VTT. Ingestion takes about a minute; the Sources list below updates automatically.</p>
                </>
              ) : (
                <>
                  <input required value={book.title} onChange={(e) => setBook({ ...book, title: e.target.value })} placeholder="Book title" className="w-full rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-stone-400" />
                  <input value={book.author} onChange={(e) => setBook({ ...book, author: e.target.value })} placeholder="Author (optional)" className="w-full rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-stone-400" />
                  <input required type="file" accept="application/pdf" onChange={(e) => setBook({ ...book, file: e.target.files?.[0] ?? null })} className="block w-full text-sm text-stone-600" />
                </>
              )}
              <button disabled={busy} className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50">
                {busy ? "Submitting…" : "Ingest"}
              </button>
              {msg && <p className="text-sm text-stone-600">{msg}</p>}
            </form>
          </div>

          <div>
            <h2 className="text-xs font-medium uppercase tracking-wider text-stone-400">Sources</h2>
            <ul className="mt-3 divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white">
              {sources.map((s) => {
                const prog = jobs.find((j) => j.source_id === s.id && j.status === "running")?.progress as { pages_done?: number; pages_total?: number } | undefined;
                return (
                  <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <div className="min-w-0">
                      <div className="truncate font-medium">{s.title}</div>
                      <div className="text-xs text-stone-500">
                        {s.kind} · <span className={s.status === "ready" ? "text-emerald-700" : s.status === "failed" ? "text-red-700" : "text-amber-700"}>{s.status}</span>
                        {prog?.pages_total ? ` · ${prog.pages_done}/${prog.pages_total} pages` : ""} · {s.chunk_count} chunks
                        {s.lecture?.duration_seconds ? ` · ${fmtTime(s.lecture.duration_seconds)}` : ""}
                      </div>
                      {s.status_detail && <div className="truncate text-xs text-red-700">{s.status_detail}</div>}
                    </div>
                    <div className="flex shrink-0 gap-3 text-xs text-stone-500">
                      {s.kind === "book" && <Link href={`/admin/sources/${s.id}`} className="hover:text-stone-900">Review</Link>}
                      <button onClick={() => api.admin.reprocess(token, s.id).then(() => refresh(token)).catch((e) => setMsg(e.message))} className="hover:text-stone-900">Reprocess</button>
                      <button onClick={() => confirm(`Delete "${s.title}"?`) && api.admin.remove(token, s.id).then(() => refresh(token)).catch((e) => setMsg(e.message))} className="hover:text-red-700">Delete</button>
                    </div>
                  </li>
                );
              })}
            </ul>
            <h2 className="mt-8 text-xs font-medium uppercase tracking-wider text-stone-400">Recent jobs</h2>
            <ul className="mt-3 space-y-1 text-xs text-stone-600">
              {jobs.slice(0, 8).map((j) => (
                <li key={j.id} className="flex justify-between rounded-md bg-white px-3 py-2">
                  <span>{j.job_type} · {j.status}{j.error ? ` · ${j.error.slice(0, 80)}` : ""}</span>
                  <span className="text-stone-400">{new Date(j.created_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
    </>
  );
}
