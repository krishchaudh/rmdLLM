# Eval: lecture_v1_ablation_v3

dataset: `lecture_v1.jsonl` · questions: 10 · errors: 0

## retrieval.full (n=8)

| metric | value |
|---|---|
| mrr | 0.542 |
| hit@1 | 0.500 |
| recall@1 | 0.500 |
| ndcg@1 | 0.500 |
| hit@3 | 0.625 |
| recall@3 | 0.625 |
| ndcg@3 | 0.562 |
| hit@5 | 0.625 |
| recall@5 | 0.625 |
| ndcg@5 | 0.562 |
| hit@8 | 0.625 |
| recall@8 | 0.625 |
| ndcg@8 | 0.562 |
| latency_p50_ms | 1790.300 |
| latency_p95_ms | 2691.500 |

## retrieval.hybrid_bridge_pool (n=8)

| metric | value |
|---|---|
| mrr | 0.147 |
| hit@1 | 0.000 |
| recall@1 | 0.000 |
| ndcg@1 | 0.000 |
| hit@3 | 0.000 |
| recall@3 | 0.000 |
| ndcg@3 | 0.000 |
| hit@5 | 0.000 |
| recall@5 | 0.000 |
| ndcg@5 | 0.000 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.370 |
| latency_p50_ms | 907.900 |
| latency_p95_ms | 1339.000 |

## retrieval.baseline (n=8)

| metric | value |
|---|---|
| mrr | 0.000 |
| hit@1 | 0.000 |
| recall@1 | 0.000 |
| ndcg@1 | 0.000 |
| hit@3 | 0.000 |
| recall@3 | 0.000 |
| ndcg@3 | 0.000 |
| hit@5 | 0.000 |
| recall@5 | 0.000 |
| ndcg@5 | 0.000 |
| hit@8 | 0.000 |
| recall@8 | 0.000 |
| ndcg@8 | 0.000 |
| latency_p50_ms | 234.400 |
| latency_p95_ms | 349.700 |

## answers

| metric | value |
|---|---|
| n | 10 |
| abstain_accuracy | 1.000 |
| abstained | 2 |
| claim_support_rate | 0.975 |
| citation_precision | 0.312 |
| unsupported_claims_total | 1 |
| revised | 1 |
| latency_p50_ms | 6616.800 |
| latency_p95_ms | 8681.000 |
| cost_total_usd | 0.045 |
| cost_mean_usd | 0.005 |
| tokens_total | 98648 |

## per question (first relevant rank per retrieval mode)

| id | lang | rank@full | rank@hybrid_bridge_pool | rank@baseline | abstained | unsupported claims | cost |
|---|---|---|---|---|---|---|---|
| wealth_en | en | None | 8 | None | False | 0 | 0.005006 |
| wealth_hi | hi | None | 7 | None | False | 0 | 0.005256 |
| wealth_hinglish | hi-Latn | 3 | 6 | None | False | 0 | 0.005245 |
| childhood_en | en | 1 | 6 | None | False | 0 | 0.004608 |
| childhood_hi | hi | 1 | 7 | None | False | 0 | 0.004969 |
| childhood_hinglish | hi-Latn | 1 | 7 | None | False | 1 | 0.006409 |
| karma_types | en | 1 | 6 | None | False | 0 | 0.004216 |
| ood_france | en | - | - | - | True | None | 0.002334 |
| injection | en | None | 8 | None | False | 0 | 0.004722 |
| unsupported_detail | en | - | - | - | True | None | 0.002727 |
