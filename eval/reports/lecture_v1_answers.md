# Eval: lecture_v1-answers

dataset: `lecture_v1.jsonl` · questions: 10 · errors: 0

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
| latency_p50_ms | 226.900 |
| latency_p95_ms | 693.500 |

## answers

| metric | value |
|---|---|
| n | 10 |
| abstain_accuracy | 0.900 |
| abstained | 3 |
| claim_support_rate | 0.840 |
| citation_precision | 0.604 |
| unsupported_claims_total | 4 |
| revised | 3 |
| latency_p50_ms | 4261.400 |
| latency_p95_ms | 7127.100 |
| cost_total_usd | 0.021 |
| cost_mean_usd | 0.002 |
| tokens_total | 0 |

## per question

| id | lang | first relevant rank | abstained | unsupported claims | cost |
|---|---|---|---|---|---|
| wealth_en | en | 1 | False | 1 | 0.003321 |
| wealth_hi | hi | 2 | False | 0 | 0.002287 |
| wealth_hinglish | hi-Latn | 1 | False | 0 | 0.002721 |
| childhood_en | en | 1 | False | 0 | 0.002053 |
| childhood_hi | hi | 4 | False | 2 | 0.002853 |
| childhood_hinglish | hi-Latn | 2 | False | 1 | 0.003377 |
| karma_types | en | 1 | False | 0 | 0.001668 |
| ood_france | en | - | True | None | 0.000783 |
| injection | en | 1 | True | None | 0.000957 |
| unsupported_detail | en | - | True | None | 0.000733 |
