# Eval: lecture_v1_ablation

dataset: `lecture_v1.jsonl` · questions: 10 · errors: 0

## retrieval.full (n=8)

| metric | value |
|---|---|
| mrr | 0.676 |
| hit@1 | 0.625 |
| recall@1 | 0.625 |
| ndcg@1 | 0.625 |
| hit@3 | 0.625 |
| recall@3 | 0.625 |
| ndcg@3 | 0.432 |
| hit@5 | 0.625 |
| recall@5 | 0.625 |
| ndcg@5 | 0.494 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.675 |
| latency_p50_ms | 1835.400 |
| latency_p95_ms | 2999.900 |

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
| latency_p50_ms | 217.300 |
| latency_p95_ms | 422.000 |

## retrieval.hybrid_only (n=8)

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
| latency_p50_ms | 231.500 |
| latency_p95_ms | 531.300 |

## retrieval.hybrid_bridge_pool (n=8)

| metric | value |
|---|---|
| mrr | 0.833 |
| hit@1 | 0.750 |
| recall@1 | 0.750 |
| ndcg@1 | 0.750 |
| hit@3 | 0.875 |
| recall@3 | 0.875 |
| ndcg@3 | 0.702 |
| hit@5 | 0.875 |
| recall@5 | 0.875 |
| ndcg@5 | 0.768 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.848 |
| latency_p50_ms | 1061.400 |
| latency_p95_ms | 1212.800 |

## answers

| metric | value |
|---|---|
| n | 10 |
| abstain_accuracy | 1.000 |
| abstained | 2 |
| claim_support_rate | 0.938 |
| citation_precision | 0.528 |
| unsupported_claims_total | 2 |
| revised | 1 |
| latency_p50_ms | 6303.600 |
| latency_p95_ms | 7634.200 |
| cost_total_usd | 0.039 |
| cost_mean_usd | 0.004 |
| tokens_total | 81067 |

## per question (first relevant rank per retrieval mode)

| id | lang | rank@full | rank@baseline | rank@hybrid_only | rank@hybrid_bridge_pool | abstained | unsupported claims | cost |
|---|---|---|---|---|---|---|---|---|
| wealth_en | en | 8 | None | None | 1 | False | 0 | 0.004416 |
| wealth_hi | hi | 7 | None | None | 1 | False | 0 | 0.004387 |
| wealth_hinglish | hi-Latn | 7 | None | None | 1 | False | 0 | 0.004773 |
| childhood_en | en | 1 | None | None | 1 | False | 0 | 0.003917 |
| childhood_hi | hi | 1 | None | None | 1 | False | 2 | 0.005132 |
| childhood_hinglish | hi-Latn | 1 | None | None | 2 | False | 0 | 0.004263 |
| karma_types | en | 1 | None | None | 6 | False | 0 | 0.003561 |
| ood_france | en | - | - | - | - | True | None | 0.001818 |
| injection | en | 1 | None | None | 1 | False | 0 | 0.004086 |
| unsupported_detail | en | - | - | - | - | True | None | 0.0022 |
