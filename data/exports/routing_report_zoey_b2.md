# Routing evaluation (zoey_b2, 120 labeled items, 30 errors)

Rules flagged 25 items; 22 of them were labeled errors.

| Signal | AUC |
| --- | --- |
| LLM judge severity alone | 0.82 |
| Rules first, then LLM severity | 0.96 |

## Operating table (risk target: ≤ 2 errors per 100 auto-shipped)

| Policy | Auto-ship if | Auto-shipped | Review saved | Errors slipped | Per 100 shipped | Meets target |
| --- | --- | --- | --- | --- | --- | --- |
| LLM only | severity ≤ 1 | 74 | 62% | 7/30 | 9.5 | no |
| LLM only | severity ≤ 2 | 88 | 73% | 9/30 | 10.2 | no |
| LLM only | severity ≤ 3 | 104 | 87% | 16/30 | 15.4 | no |
| LLM only | severity ≤ 4 | 110 | 92% | 20/30 | 18.2 | no |
| LLM only | severity ≤ 5 | 112 | 93% | 22/30 | 19.6 | no |
| Rules + LLM | severity ≤ 1 | 66 | 55% | 1/30 | 1.5 | yes |
| Rules + LLM | severity ≤ 2 | 77 | 64% | 1/30 | 1.3 | yes |
| Rules + LLM | severity ≤ 3 | 89 | 74% | 4/30 | 4.5 | no |
| Rules + LLM | severity ≤ 4 | 94 | 78% | 7/30 | 7.4 | no |
| Rules + LLM | severity ≤ 5 | 95 | 79% | 8/30 | 8.4 | no |

Held-out check: the rules were frozen (git commit) before these batches were translated or labeled.