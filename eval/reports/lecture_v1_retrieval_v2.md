# Eval: lecture_v1_retrieval_v2

dataset: `lecture_v1.jsonl` · questions: 10 · errors: 0

## retrieval.hybrid (n=8)

| metric | value |
|---|---|
| mrr | 0.674 |
| hit@1 | 0.625 |
| recall@1 | 0.625 |
| ndcg@1 | 0.625 |
| hit@3 | 0.625 |
| recall@3 | 0.625 |
| ndcg@3 | 0.528 |
| hit@5 | 0.625 |
| recall@5 | 0.625 |
| ndcg@5 | 0.591 |
| hit@8 | 1.000 |
| recall@8 | 1.000 |
| ndcg@8 | 0.711 |
| latency_p50_ms | 1752.100 |
| latency_p95_ms | 2438.200 |

## per question (first relevant rank per retrieval mode)

| id | lang | rank@hybrid | abstained | unsupported claims | cost |
|---|---|---|---|---|---|
| wealth_en | en | 8 | - | - | - |
| wealth_hi | hi | 7 | - | - | - |
| wealth_hinglish | hi-Latn | 8 | - | - | - |
| childhood_en | en | 1 | - | - | - |
| childhood_hi | hi | 1 | - | - | - |
| childhood_hinglish | hi-Latn | 1 | - | - | - |
| karma_types | en | 1 | - | - | - |
| ood_france | en | - | - | - | - |
| injection | en | 1 | - | - | - |
| unsupported_detail | en | - | - | - | - |
