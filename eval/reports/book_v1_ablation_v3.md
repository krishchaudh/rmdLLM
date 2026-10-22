# Eval: book_v1_ablation_v3

dataset: `book_v1.jsonl` · questions: 19 · errors: 0

## retrieval.full (n=16)

| metric | value |
|---|---|
| mrr | 0.806 |
| hit@1 | 0.750 |
| recall@1 | 0.750 |
| ndcg@1 | 0.750 |
| hit@3 | 0.812 |
| recall@3 | 0.812 |
| ndcg@3 | 0.736 |
| hit@5 | 0.938 |
| recall@5 | 0.938 |
| ndcg@5 | 0.813 |
| hit@8 | 0.938 |
| recall@8 | 0.938 |
| ndcg@8 | 0.823 |
| latency_p50_ms | 1826.400 |
| latency_p95_ms | 2525.600 |

## retrieval.hybrid_bridge_pool (n=16)

| metric | value |
|---|---|
| mrr | 0.507 |
| hit@1 | 0.375 |
| recall@1 | 0.375 |
| ndcg@1 | 0.375 |
| hit@3 | 0.625 |
| recall@3 | 0.625 |
| ndcg@3 | 0.483 |
| hit@5 | 0.750 |
| recall@5 | 0.750 |
| ndcg@5 | 0.578 |
| hit@8 | 0.750 |
| recall@8 | 0.750 |
| ndcg@8 | 0.578 |
| latency_p50_ms | 933.900 |
| latency_p95_ms | 1132.400 |

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
| latency_p50_ms | 225.200 |
| latency_p95_ms | 447.100 |

## answers

| metric | value |
|---|---|
| n | 19 |
| abstain_accuracy | 0.947 |
| abstained | 2 |
| claim_support_rate | 1.000 |
| citation_precision | 0.406 |
| unsupported_claims_total | 0 |
| revised | 0 |
| latency_p50_ms | 7525.300 |
| latency_p95_ms | 7965.700 |
| cost_total_usd | 0.093 |
| cost_mean_usd | 0.005 |
| tokens_total | 196912 |

## per question (first relevant rank per retrieval mode)

| id | lang | rank@full | rank@hybrid_bridge_pool | rank@baseline | abstained | unsupported claims | cost |
|---|---|---|---|---|---|---|---|
| book_01_hi | hi | 1 | 3 | 1 | False | 0 | 0.005069 |
| book_02_en | en | 1 | 1 | 1 | False | 0 | 0.005132 |
| book_03_en | en | 1 | 5 | 2 | False | 0 | 0.005266 |
| book_04_en | en | 1 | 1 | 1 | False | 0 | 0.005206 |
| book_05_en | en | 1 | 1 | 1 | False | 0 | 0.005724 |
| book_06_en | en | 5 | None | None | False | 0 | 0.005077 |
| book_07_en | en | 1 | 4 | 1 | False | 0 | 0.00518 |
| book_08_hi | hi | 1 | 2 | 1 | False | 0 | 0.005293 |
| book_09_en | en | 1 | 1 | 1 | False | 0 | 0.004958 |
| book_10_hi | hi | None | None | None | False | 0 | 0.005453 |
| book_11_en | en | 2 | 2 | 1 | False | 0 | 0.005394 |
| book_12_hilatn | hi-Latn | 5 | None | 8 | False | 0 | 0.005368 |
| book_13_hilatn | hi-Latn | 1 | 1 | 1 | False | 0 | 0.005291 |
| book_14_en | en | 1 | 3 | 1 | False | 0 | 0.006194 |
| book_15_hilatn | hi-Latn | 1 | 1 | 1 | False | 0 | 0.005244 |
| book_16_en | en | 1 | None | 1 | False | 0 | 0.004526 |
| abstain_fifa_en | en | - | - | - | True | None | 0.002389 |
| abstain_bio_hi | hi | - | - | - | False | 0 | 0.004323 |
| abstain_stock_en | en | - | - | - | True | None | 0.002283 |
