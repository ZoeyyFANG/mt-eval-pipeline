# QE evaluation report (zoey, 200 labeled items)

Errors: 43 · acceptable: 157.
**Warning:** fewer than 50 items in a class; treat AUCs as provisional.

## Label reliability

50 items labeled by both: agreement 96%, Cohen's kappa 0.88.

## Separability (ROC AUC, 95% CI)

| Signal | Live? | n | AUC | 95% CI |
| --- | --- | --- | --- | --- |
| LLM judge severity (QE) | yes | 200 | 0.84 | 0.77–0.91 |
| chrF++ (needs reference; validation only) | no | 200 | 0.81 | 0.75–0.87 |

## AUC by stratum

| Signal | Stratum | errors / acceptable | AUC |
| --- | --- | --- | --- |
| LLM judge severity (QE) | colors | 3 / 6 | too few |
| LLM judge severity (QE) | dnt | 4 / 5 | too few |
| LLM judge severity (QE) | error | 4 / 18 | too few |
| LLM judge severity (QE) | long | 7 / 13 | 0.68 |
| LLM judge severity (QE) | medium | 7 / 44 | 0.56 |
| LLM judge severity (QE) | placeholder_markup | 12 / 25 | 0.97 |
| LLM judge severity (QE) | short | 6 / 46 | 0.99 |
| chrF++ (needs reference; validation only) | colors | 3 / 6 | too few |
| chrF++ (needs reference; validation only) | dnt | 4 / 5 | too few |
| chrF++ (needs reference; validation only) | error | 4 / 18 | too few |
| chrF++ (needs reference; validation only) | long | 7 / 13 | 0.64 |
| chrF++ (needs reference; validation only) | medium | 7 / 44 | 0.80 |
| chrF++ (needs reference; validation only) | placeholder_markup | 12 / 25 | 0.91 |
| chrF++ (needs reference; validation only) | short | 6 / 46 | 0.94 |

## Operating point (risk target: ≤ 2 errors per 100 unreviewed)

- LLM judge severity (QE): no threshold meets the risk target; everything needs review.

Rule-based token check flagged 8 labeled items; 8 of them were labeled as errors.
