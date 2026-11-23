# Routing evaluation (zoey_b2, 120 labeled items, 29 errors)

Rules flagged 25 items; 21 of them were labeled errors.

| Signal | AUC |
| --- | --- |
| LLM judge severity alone | 0.84 |
| Rules first, then LLM severity | 0.95 |

## Operating table (risk target: ≤ 2 errors per 100 auto-shipped)

| Policy | Auto-ship if | Auto-shipped | Review saved | Errors slipped | Per 100 shipped | Meets target |
| --- | --- | --- | --- | --- | --- | --- |
| LLM only | severity ≤ 1 | 74 | 62% | 6/29 | 8.1 | no |
| LLM only | severity ≤ 2 | 88 | 73% | 8/29 | 9.1 | no |
| LLM only | severity ≤ 3 | 104 | 87% | 15/29 | 14.4 | no |
| LLM only | severity ≤ 4 | 110 | 92% | 19/29 | 17.3 | no |
| LLM only | severity ≤ 5 | 112 | 93% | 21/29 | 18.8 | no |
| Rules + LLM | severity ≤ 1 | 66 | 55% | 1/29 | 1.5 | yes |
| Rules + LLM | severity ≤ 2 | 77 | 64% | 1/29 | 1.3 | yes |
| Rules + LLM | severity ≤ 3 | 89 | 74% | 4/29 | 4.5 | no |
| Rules + LLM | severity ≤ 4 | 94 | 78% | 7/29 | 7.4 | no |
| Rules + LLM | severity ≤ 5 | 95 | 79% | 8/29 | 8.4 | no |

Held-out check: the rules were frozen (git commit) before these batches were translated or labeled.