"""Evaluation runner: retrieval quality, answer faithfulness, citation correctness, latency, cost.

Dataset = JSONL, one question per line:
  {"id": "wealth_en", "question": "...", "language": "en",
   "expected": [{"kind": "lecture", "youtube_id": "...", "start_seconds": 316, "end_seconds": 394}],
   "should_abstain": false, "tags": ["lecture", "acceptance"]}
Questions with "should_abstain": true have no expected locators; they test refusal.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from rmd.eval.metrics import (
    hit_at_k,
    is_relevant,
    mean,
    mrr,
    ndcg_at_k,
    percentile,
    recall_at_k,
    relevance_vector,
)
from rmd.models import EvalRun
from rmd.retrieval.search import Hit, retrieve

KS = (1, 3, 5, 8)


@dataclass
class QuestionResult:
    id: str
    question: str
    language: str
    tags: list[str]
    should_abstain: bool
    retrieval: dict = field(default_factory=dict)
    answer: dict | None = None
    error: str | None = None


def load_dataset(path: str | Path) -> list[dict]:
    rows = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            rows.append(json.loads(ln))
    return rows


def _hit_dict(h: Hit) -> dict:
    return {
        "chunk_id": str(h.chunk_id),
        "kind": h.kind,
        "title": h.title,
        "youtube_id": h.youtube_id,
        "locator": h.locator,
        "score": h.score,
    }


def eval_retrieval(db: Session, q: dict, *, mode: str, k: int) -> dict:
    t = time.perf_counter()
    res = retrieve(db, q["question"], k=k, mode=mode)
    elapsed = (time.perf_counter() - t) * 1000
    hits = [_hit_dict(h) for h in res.hits]
    expected = q.get("expected", [])
    rel = relevance_vector(hits, expected) if expected else []
    out = {
        "mode": mode,
        "latency_ms": round(elapsed, 1),
        "hits": hits,
        "expanded_terms": res.expanded_terms,
        "translated_query": res.translated_query,
    }
    if expected:
        out.update(
            {
                "mrr": mrr(rel),
                **{f"hit@{kk}": hit_at_k(rel, kk) for kk in KS if kk <= k},
                **{f"recall@{kk}": recall_at_k(rel, expected, hits, kk) for kk in KS if kk <= k},
                **{f"ndcg@{kk}": ndcg_at_k(rel, kk) for kk in KS if kk <= k},
                "first_relevant_rank": (rel.index(1) + 1) if 1 in rel else None,
            }
        )
    return out


def eval_answer(db: Session, q: dict, *, mode: str, k: int) -> dict:
    from rmd.generation.answer import answer_question

    a = answer_question(db, q["question"], k=k, mode=mode)
    expected = q.get("expected", [])
    cited = [c for c in a.citations if f"[{c['n']}]" in a.answer]
    cited_hits = [
        {"kind": c["kind"], "youtube_id": c.get("youtube_id"), "title": c["title"], "locator": c}
        for c in cited
    ]
    cited_relevant = (
        sum(1 for h in cited_hits if any(is_relevant(h, e) for e in expected)) if expected else None
    )
    ver = a.verification or {}
    total = ver.get("claims_total")
    unsupported = ver.get("claims_unsupported")
    return {
        "abstained": a.abstained,
        "abstain_correct": a.abstained == q.get("should_abstain", False)
        or (a.abstained and bool(q.get("abstain_ok"))),
        "answer": a.answer,
        "language": a.language,
        "citations_used": len(cited),
        "citations_relevant": cited_relevant,
        "citation_precision": (cited_relevant / len(cited)) if (expected and cited) else None,
        "claims_total": total,
        "claims_unsupported": unsupported,
        "claim_support_rate": (1 - unsupported / total) if total else None,
        "invalid_citations_removed": ver.get("invalid_citations_removed", 0),
        "revised": bool(ver.get("revised")),
        "latency_ms": a.latency_ms,
        "total_latency_ms": round(
            sum(v for v in a.latency_ms.values() if isinstance(v, int | float)), 1
        ),
        "usage": a.usage,
        "estimated_cost_usd": a.estimated_cost_usd,
        "model": a.model,
    }


def run(
    db: Session,
    dataset_path: str | Path,
    *,
    name: str,
    modes: tuple[str, ...] = ("hybrid",),
    k: int = 8,
    with_answers: bool = False,
    save: bool = True,
) -> dict:
    rows = load_dataset(dataset_path)
    per_q: list[dict] = []
    for q in rows:
        qr = QuestionResult(
            id=q["id"],
            question=q["question"],
            language=q.get("language", "en"),
            tags=q.get("tags", []),
            should_abstain=bool(q.get("should_abstain")),
        )
        try:
            qr.retrieval = {m: eval_retrieval(db, q, mode=m, k=k) for m in modes}
            if with_answers:
                qr.answer = eval_answer(db, q, mode=modes[0], k=k)
        except Exception as e:  # keep going; record failure
            qr.error = f"{type(e).__name__}: {e}"
        per_q.append(asdict(qr))

    metrics = summarize(per_q, modes=modes, k=k, with_answers=with_answers)
    config = {
        "modes": list(modes),
        "k": k,
        "with_answers": with_answers,
        "dataset": str(dataset_path),
    }
    report = {
        "name": name,
        "dataset": Path(dataset_path).name,
        "config": config,
        "metrics": metrics,
        "per_question": per_q,
    }
    if save:
        er = EvalRun(
            name=name,
            dataset=Path(dataset_path).name,
            config=config,
            metrics=metrics,
            per_question=per_q,
            git_sha=_git_sha(),
        )
        db.add(er)
        db.commit()
        report["eval_run_id"] = str(er.id)
    return report


def summarize(per_q: list[dict], *, modes: tuple[str, ...], k: int, with_answers: bool) -> dict:
    out: dict = {"questions": len(per_q), "errors": sum(1 for r in per_q if r["error"])}
    scored = [r for r in per_q if not r["error"] and not r["should_abstain"]]
    for m in modes:
        rs = [r["retrieval"][m] for r in scored if m in r["retrieval"]]
        if not rs:
            continue
        agg = {"n": len(rs), "mrr": mean([r["mrr"] for r in rs])}
        for kk in KS:
            if kk <= k:
                agg[f"hit@{kk}"] = mean([r[f"hit@{kk}"] for r in rs])
                agg[f"recall@{kk}"] = mean([r[f"recall@{kk}"] for r in rs])
                agg[f"ndcg@{kk}"] = mean([r[f"ndcg@{kk}"] for r in rs])
        lat = [
            r["latency_ms"]
            for r in per_q
            if not r["error"] and m in r["retrieval"]
            for r in [r["retrieval"][m]]
        ]
        agg["latency_p50_ms"] = percentile(lat, 50)
        agg["latency_p95_ms"] = percentile(lat, 95)
        out[f"retrieval.{m}"] = agg
    if with_answers:
        ans = [r["answer"] for r in per_q if r["answer"]]
        if ans:
            supp = [a["claim_support_rate"] for a in ans if a["claim_support_rate"] is not None]
            prec = [a["citation_precision"] for a in ans if a["citation_precision"] is not None]
            lat = [a["total_latency_ms"] for a in ans]
            cost = [a["estimated_cost_usd"] for a in ans]
            out["answer"] = {
                "n": len(ans),
                "abstain_accuracy": mean([1.0 if a["abstain_correct"] else 0.0 for a in ans]),
                "abstained": sum(1 for a in ans if a["abstained"]),
                "claim_support_rate": mean(supp) if supp else None,
                "citation_precision": mean(prec) if prec else None,
                "unsupported_claims_total": sum(a["claims_unsupported"] or 0 for a in ans),
                "revised": sum(1 for a in ans if a["revised"]),
                "latency_p50_ms": percentile(lat, 50),
                "latency_p95_ms": percentile(lat, 95),
                "cost_total_usd": round(sum(cost), 5),
                "cost_mean_usd": round(statistics.fmean(cost), 6) if cost else 0.0,
                "tokens_total": sum(_tokens(a["usage"]) for a in ans),
            }
    return out


def _tokens(usage: dict) -> int:
    if not isinstance(usage, dict):
        return 0
    return sum(
        int(v.get("prompt", 0)) + int(v.get("completion", 0))
        for v in usage.values()
        if isinstance(v, dict)
    )


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()[:40]
    except Exception:
        return None


def format_markdown(report: dict) -> str:
    m = report["metrics"]
    lines = [
        f"# Eval: {report['name']}",
        "",
        f"dataset: `{report['dataset']}` · questions: {m['questions']} · errors: {m['errors']}",
        "",
    ]
    for key, agg in m.items():
        if not key.startswith("retrieval."):
            continue
        lines += [f"## {key} (n={agg['n']})", "", "| metric | value |", "|---|---|"]
        for mk, v in agg.items():
            if mk != "n":
                lines.append(f"| {mk} | {v:.3f} |" if isinstance(v, float) else f"| {mk} | {v} |")
        lines.append("")
    if "answer" in m:
        a = m["answer"]
        lines += ["## answers", "", "| metric | value |", "|---|---|"]
        for mk, v in a.items():
            lines.append(f"| {mk} | {v:.3f} |" if isinstance(v, float) else f"| {mk} | {v} |")
        lines.append("")
    modes = [k.split(".", 1)[1] for k in m if k.startswith("retrieval.")]
    head = " | ".join(f"rank@{md}" for md in modes)
    lines += [
        "## per question (first relevant rank per retrieval mode)",
        "",
        f"| id | lang | {head} | abstained | unsupported claims | cost |",
        "|---|---|" + "---|" * len(modes) + "---|---|---|",
    ]
    for r in report["per_question"]:
        ranks = " | ".join(
            str((r["retrieval"].get(md) or {}).get("first_relevant_rank", "-")) for md in modes
        )
        a = r["answer"] or {}
        lines.append(
            f"| {r['id']} | {r['language']} | {ranks} | "
            f"{a.get('abstained', '-')} | {a.get('claims_unsupported', '-')} | {a.get('estimated_cost_usd', '-')} |"
        )
    return "\n".join(lines) + "\n"
