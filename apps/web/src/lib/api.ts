export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Citation = {
  n: number;
  chunk_id: string;
  source_id: string;
  kind: "book" | "lecture";
  title: string;
  language: string;
  text: string;
  where: string;
  url: string | null;
  start_seconds?: number;
  end_seconds?: number;
  youtube_id?: string | null;
  page_index?: number;
  page_index_end?: number | null;
  printed_page_number?: string | null;
};

export type AskResponse = {
  conversation_id: string;
  message_id: string;
  answer: string;
  abstained: boolean;
  citations: Citation[];
  followups: string[];
  language: string;
  latency_ms: Record<string, number>;
  verification_summary: Record<string, unknown>;
};

export type Source = {
  id: string;
  kind: "book" | "lecture";
  title: string;
  language: string;
  status: string;
  status_detail: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
  book: { page_count: number; author: string | null; file_size: number } | null;
  lecture: {
    youtube_id: string;
    url: string;
    channel: string | null;
    duration_seconds: number | null;
    metadata_status: string;
  } | null;
};

export type Job = {
  id: string;
  source_id: string;
  job_type: string;
  status: string;
  attempts: number;
  progress: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ConversationSummary = {
  id: string;
  title: string | null;
  language: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  abstained: boolean;
  followups: string[];
  created_at: string;
};

export type Page = {
  page_index: number;
  printed_page_number: string | null;
  text: string;
  extraction_method: string;
  ocr_confidence: number | null;
  needs_review: boolean;
  review_reason: string | null;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    let raw: unknown;
    try {
      const j = await res.json();
      raw = j.detail ?? j;
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(raw);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, raw);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type StreamEvent =
  | { type: "status"; stage: "retrieval" | "generation" | "verification" }
  | { type: "token"; text: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "done"; response: AskResponse }
  | { type: "error"; detail: string };

async function askStream(
  question: string,
  conversation_id: string | null | undefined,
  onEvent: (e: StreamEvent) => void,
  token?: string | null,
): Promise<AskResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "text/event-stream" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/ask/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ question, conversation_id: conversation_id ?? null }),
    cache: "no-store",
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    let raw: unknown;
    try {
      const j = await res.json();
      raw = j.detail ?? j;
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(raw);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, raw);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let done: AskResponse | null = null;
  for (;;) {
    const { value, done: eof } = await reader.read();
    if (eof) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const data = frame
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim())
        .join("");
      if (!data) continue;
      const ev = JSON.parse(data) as StreamEvent;
      if (ev.type === "error") throw new ApiError(503, ev.detail);
      if (ev.type === "done") done = ev.response;
      onEvent(ev);
    }
  }
  if (!done) throw new ApiError(502, "The answer stream ended unexpectedly, please retry");
  return done;
}

export const api = {
  ask: (question: string, conversation_id?: string | null, token?: string | null) =>
    request<AskResponse>(
      "/ask",
      { method: "POST", body: JSON.stringify({ question, conversation_id: conversation_id ?? null }) },
      token,
    ),
  askStream,
  conversation: (id: string, token?: string | null) =>
    request<{ id: string; title: string | null; owned: boolean; messages: StoredMessage[] }>(
      `/conversations/${id}`,
      {},
      token,
    ),
  me: {
    conversations: (t: string) => request<ConversationSummary[]>("/me/conversations", {}, t),
    rename: (t: string, id: string, title: string) =>
      request<ConversationSummary>(
        `/me/conversations/${id}`,
        { method: "PATCH", body: JSON.stringify({ title }) },
        t,
      ),
    remove: (t: string, id: string) => request<void>(`/me/conversations/${id}`, { method: "DELETE" }, t),
    claim: (t: string, id: string) =>
      request<void>(`/me/conversations/${id}/claim`, { method: "POST" }, t),
    removeAll: (t: string) => request<void>("/me/conversations", { method: "DELETE" }, t),
    deleteAccount: (t: string) =>
      request<{ history_deleted: boolean; account_deleted: boolean }>("/me", { method: "DELETE" }, t),
  },
  feedback: (message_id: string, rating: 1 | -1, comment?: string) =>
    request("/feedback", { method: "POST", body: JSON.stringify({ message_id, rating, comment }) }),
  sources: () => request<Source[]>("/sources"),
  source: (id: string) => request<Source>(`/sources/${id}`),
  page: (id: string, idx: number) => request<Page>(`/sources/${id}/pages/${idx}`),
  pdfUrl: (id: string) => `${API_BASE}/sources/${id}/pdf`,
  pageImageUrl: (id: string, idx: number, dpi = 110) =>
    `${API_BASE}/sources/${id}/pages/${idx}/image?dpi=${dpi}`,
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  admin: {
    jobs: (t: string) => request<Job[]>("/admin/jobs", {}, t),
    stats: (t: string) => request<Record<string, unknown>>("/admin/stats", {}, t),
    fetchTranscript: (t: string, url: string) =>
      request<{ video_id: string; language: string; transcript: string; segments: number }>(
        "/admin/lectures/transcript",
        { method: "POST", body: JSON.stringify({ url }) },
        t,
      ),
    addLecture: (t: string, body: { url: string; transcript: string; title?: string; replace?: boolean }) =>
      request("/admin/lectures", { method: "POST", body: JSON.stringify(body) }, t),
    lookupLecture: (t: string, url: string) =>
      request<{ video_id: string; existing: Source | null; reason: string | null }>(
        `/admin/lectures/lookup?url=${encodeURIComponent(url)}`,
        {},
        t,
      ),
    uploadBook: (t: string, form: FormData) =>
      request("/admin/books", { method: "POST", body: form }, t),
    reprocess: (t: string, id: string) =>
      request(`/admin/sources/${id}/reprocess`, { method: "POST" }, t),
    remove: (t: string, id: string) => request(`/admin/sources/${id}`, { method: "DELETE" }, t),
    pages: (t: string, id: string, needsReview: boolean | null, offset = 0, limit = 30) =>
      request<Page[]>(
        `/admin/sources/${id}/pages?offset=${offset}&limit=${limit}` +
          (needsReview === null ? "" : `&needs_review=${needsReview}`),
        {},
        t,
      ),
    updatePage: (t: string, id: string, idx: number, body: Partial<Page>) =>
      request<Page>(`/admin/sources/${id}/pages/${idx}`, { method: "PATCH", body: JSON.stringify(body) }, t),
  },
};

export function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export const hasDevanagari = (s: string) => /[\u0900-\u097F]/.test(s);
