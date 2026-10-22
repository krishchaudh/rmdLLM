# Eval: book_v1_ablation

dataset: `book_v1.jsonl` · questions: 19 · errors: 0

## retrieval.full (n=16)

| metric | value |
|---|---|
| mrr | 0.500 |
| hit@1 | 0.438 |
| recall@1 | 0.438 |
| ndcg@1 | 0.438 |
| hit@3 | 0.562 |
| recall@3 | 0.562 |
| ndcg@3 | 0.468 |
| hit@5 | 0.562 |
| recall@5 | 0.562 |
| ndcg@5 | 0.499 |
| hit@8 | 0.562 |
| recall@8 | 0.562 |
| ndcg@8 | 0.499 |
| latency_p50_ms | 1806.900 |
| latency_p95_ms | 2049.100 |

## retrieval.baseline (n=16)

| metric | value |
|---|---|
| mrr | 0.789 |
| hit@1 | 0.750 |
| recall@1 | 0.750 |
| ndcg@1 | 0.750 |
| hit@3 | 0.812 |
| recall@3 | 0.812 |
| ndcg@3 | 0.717 |
| hit@5 | 0.812 |
| recall@5 | 0.812 |
| ndcg@5 | 0.730 |
| hit@8 | 0.875 |
| recall@8 | 0.875 |
| ndcg@8 | 0.779 |
| latency_p50_ms | 227.600 |
| latency_p95_ms | 329.000 |

## retrieval.hybrid_only (n=16)

| metric | value |
|---|---|
| mrr | 0.515 |
| hit@1 | 0.375 |
| recall@1 | 0.375 |
| ndcg@1 | 0.375 |
| hit@3 | 0.562 |
| recall@3 | 0.562 |
| ndcg@3 | 0.445 |
| hit@5 | 0.812 |
| recall@5 | 0.812 |
| ndcg@5 | 0.544 |
| hit@8 | 0.812 |
| recall@8 | 0.812 |
| ndcg@8 | 0.580 |
| latency_p50_ms | 225.200 |
| latency_p95_ms | 358.900 |

## retrieval.hybrid_bridge_pool (n=16)

| metric | value |
|---|---|
| mrr | 0.356 |
| hit@1 | 0.250 |
| recall@1 | 0.250 |
| ndcg@1 | 0.250 |
| hit@3 | 0.438 |
| recall@3 | 0.438 |
| ndcg@3 | 0.372 |
| hit@5 | 0.500 |
| recall@5 | 0.500 |
| ndcg@5 | 0.396 |
| hit@8 | 0.500 |
| recall@8 | 0.500 |
| ndcg@8 | 0.396 |
| latency_p50_ms | 994.400 |
| latency_p95_ms | 1166.300 |

## answers

| metric | value |
|---|---|
| n | 19 |
| abstain_accuracy | 1.000 |
| abstained | 3 |
| claim_support_rate | 1.000 |
| citation_precision | 0.363 |
| unsupported_claims_total | 0 |
| revised | 0 |
| latency_p50_ms | 6193.900 |
| latency_p95_ms | 7987.800 |
| cost_total_usd | 0.068 |
| cost_mean_usd | 0.004 |
| tokens_total | 139074 |

## per question (first relevant rank per retrieval mode)

| id | lang | rank@full | rank@baseline | rank@hybrid_only | rank@hybrid_bridge_pool | abstained | unsupported claims | cost |
|---|---|---|---|---|---|---|---|---|
| book_01_hi | hi | 1 | 1 | 1 | 5 | False | 0 | 0.003452 |
| book_02_en | en | 1 | 1 | 1 | 1 | False | 0 | 0.003645 |
| book_03_en | en | None | 2 | 5 | None | False | 0 | 0.004028 |
| book_04_en | en | 1 | 1 | 1 | 2 | False | 0 | 0.003838 |
| book_05_en | en | 1 | 1 | 1 | 1 | False | 0 | 0.004283 |
| book_06_en | en | None | None | None | None | False | 0 | 0.004 |
| book_07_en | en | 2 | 1 | 4 | None | False | 0 | 0.003676 |
| book_08_hi | hi | None | 1 | 2 | None | False | 0 | 0.003381 |
| book_09_en | en | 1 | 1 | 3 | 2 | False | 0 | 0.0033 |
| book_10_hi | hi | None | None | None | None | False | 0 | 0.00408 |
| book_11_en | en | 2 | 1 | 1 | 2 | False | 0 | 0.004191 |
| book_12_hilatn | hi-Latn | None | 8 | None | None | False | 0 | 0.004892 |
| book_13_hilatn | hi-Latn | 1 | 1 | 2 | 1 | False | 0 | 0.004636 |
| book_14_en | en | None | 1 | 5 | None | False | 0 | 0.003558 |
| book_15_hilatn | hi-Latn | 1 | 1 | 1 | 1 | False | 0 | 0.004339 |
| book_16_en | en | None | 1 | 4 | None | False | 0 | 0.003469 |
| abstain_fifa_en | en | - | - | - | - | True | None | 0.001711 |
| abstain_bio_hi | hi | - | - | - | - | True | None | 0.002055 |
| abstain_stock_en | en | - | - | - | - | True | None | 0.001799 |
