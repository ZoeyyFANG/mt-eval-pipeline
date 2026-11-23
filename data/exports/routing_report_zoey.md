# Routing evaluation (zoey, 200 labeled items, 43 errors)

Rules flagged 30 items; 28 of them were labeled errors.

| Signal | AUC |
| --- | --- |
| LLM judge severity alone | 0.84 |
| Rules first, then LLM severity | 0.98 |

## Operating table (risk target: ≤ 2 errors per 100 auto-shipped)

| Policy | Auto-ship if | Auto-shipped | Review saved | Errors slipped | Per 100 shipped | Meets target |
| --- | --- | --- | --- | --- | --- | --- |
| LLM only | severity ≤ 1 | 134 | 67% | 9/43 | 6.7 | no |
| LLM only | severity ≤ 2 | 152 | 76% | 14/43 | 9.2 | no |
| LLM only | severity ≤ 3 | 179 | 90% | 24/43 | 13.4 | no |
| LLM only | severity ≤ 4 | 191 | 96% | 34/43 | 17.8 | no |
| LLM only | severity ≤ 5 | 192 | 96% | 35/43 | 18.2 | no |
| Rules + LLM | severity ≤ 1 | 124 | 62% | 0/43 | 0.0 | yes |
| Rules + LLM | severity ≤ 2 | 140 | 70% | 3/43 | 2.1 | no |
| Rules + LLM | severity ≤ 3 | 159 | 80% | 6/43 | 3.8 | no |
| Rules + LLM | severity ≤ 4 | 170 | 85% | 15/43 | 8.8 | no |
| Rules + LLM | severity ≤ 5 | 170 | 85% | 15/43 | 8.8 | no |

Caveat: the punctuation rule was designed after reviewing these labels; confirm the rules + LLM numbers on a held-out batch before relying on them.