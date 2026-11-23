# QE evaluation report (zoey_b2, 120 labeled items)

Errors: 30 · acceptable: 90.
**Warning:** fewer than 50 items in a class; treat AUCs as provisional.

## Separability (ROC AUC, 95% CI)

| Signal | Live? | n | AUC | 95% CI |
| --- | --- | --- | --- | --- |
| LLM judge severity (QE) | yes | 120 | 0.82 | 0.73–0.91 |

## AUC by stratum

| Signal | Stratum | errors / acceptable | AUC |
| --- | --- | --- | --- |
| LLM judge severity (QE) | error | 3 / 15 | too few |
| LLM judge severity (QE) | long | 4 / 8 | too few |
| LLM judge severity (QE) | medium | 5 / 29 | 0.86 |
| LLM judge severity (QE) | placeholder_markup | 12 / 8 | 0.83 |
| LLM judge severity (QE) | short | 6 / 30 | 0.76 |

## Operating point (risk target: ≤ 2 errors per 100 unreviewed)

- LLM judge severity (QE): no threshold meets the risk target; everything needs review.

Rule-based token check flagged 8 labeled items; 8 of them were labeled as errors.
