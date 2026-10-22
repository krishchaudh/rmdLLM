# Eval: lecture_v1-retrieval

dataset: `lecture_v1.jsonl` · questions: 10 · errors: 0

## retrieval.dense (n=8)

| metric | value |
|---|---|
| mrr | 0.750 |
| hit@1 | 0.625 |
| recall@1 | 0.625 |
| ndcg@1 | 0.625 |
| hit@3 | 1.000 |
| recall@3 | 1.000 |
| ndcg@3 | 0.643 |
| hit@5 | 1.000 |
| recall@5 | 1.000 |
| ndcg@5 | 0.673 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.776 |
| latency_p50_ms | 216.200 |
| latency_p95_ms | 717.300 |

## retrieval.lexical (n=8)

| metric | value |
|---|---|
| mrr | 0.667 |
| hit@1 | 0.500 |
| recall@1 | 0.500 |
| ndcg@1 | 0.500 |
| hit@3 | 0.875 |
| recall@3 | 0.875 |
| ndcg@3 | 0.736 |
| hit@5 | 0.875 |
| recall@5 | 0.875 |
| ndcg@5 | 0.736 |
| hit@8 | 0.875 |
| recall@8 | 0.875 |
| ndcg@8 | 0.736 |
| latency_p50_ms | 1.300 |
| latency_p95_ms | 3.000 |

## retrieval.hybrid (n=8)

| metric | value |
|---|---|
| mrr | 0.781 |
| hit@1 | 0.625 |
| recall@1 | 0.625 |
| ndcg@1 | 0.625 |
| hit@3 | 0.875 |
| recall@3 | 0.875 |
| ndcg@3 | 0.635 |
| hit@5 | 1.000 |
| recall@5 | 1.000 |
| ndcg@5 | 0.719 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.770 |
| latency_p50_ms | 204.300 |
| latency_p95_ms | 311.700 |

## per question

| id | lang | first relevant rank | abstained | unsupported claims | cost |
|---|---|---|---|---|---|
| wealth_en | en | 3 | - | - | - |
| wealth_hi | hi | 3 | - | - | - |
| wealth_hinglish | hi-Latn | 1 | - | - | - |
| childhood_en | en | 1 | - | - | - |
| childhood_hi | hi | 1 | - | - | - |
| childhood_hinglish | hi-Latn | 1 | - | - | - |
| karma_types | en | 1 | - | - | - |
| ood_france | en | - | - | - | - |
| injection | en | 3 | - | - | - |
| unsupported_detail | en | - | - | - | - |
