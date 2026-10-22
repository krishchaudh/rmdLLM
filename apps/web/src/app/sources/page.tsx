import Link from "next/link";
import { Header } from "@/components/Header";
import { api, fmtTime, type Source } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  let sources: Source[] = [];
  let error: string | null = null;
  try {
    sources = await api.sources();
  } catch (e) {
    error = e instanceof Error ? e.message : "API unavailable";
  }
  return (
    <>
      <Header />
      <main className="mx-auto max-w-3xl px-5 py-12">
        <h1 className="font-serif text-4xl tracking-tight">Sources</h1>
        <p className="mt-2 text-stone-500">Everything the assistant is allowed to cite.</p>
        {error && <p className="mt-6 text-sm text-red-700">{error}</p>}
        <ul className="mt-8 divide-y divide-stone-200 border-y border-stone-200">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-4 py-4">
              <div>
                <div className="text-xs uppercase tracking-wider text-stone-400">{s.kind}</div>
                <div className="font-serif text-lg">{s.title}</div>
                <div className="text-sm text-stone-500">
                  {s.kind === "book"
                    ? `${s.book?.page_count ?? "?"} pages${s.book?.author ? ` · ${s.book.author}` : ""}`
                    : `YouTube · ${s.lecture?.duration_seconds ? fmtTime(s.lecture.duration_seconds) : ""}`}
                  {" · "}
                  <span className={s.status === "ready" ? "text-emerald-700" : "text-amber-700"}>{s.status}</span>
                </div>
              </div>
              {s.kind === "book" ? (
                <Link href={`/sources/${s.id}?page=1`} className="text-sm text-stone-700 underline-offset-4 hover:underline">
                  Read →
                </Link>
              ) : (
                <a href={s.lecture?.url} target="_blank" rel="noreferrer" className="text-sm text-stone-700 underline-offset-4 hover:underline">
                  Watch →
                </a>
              )}
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
