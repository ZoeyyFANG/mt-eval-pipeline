# Routing evaluation (zoey, 200 labeled items, 42 errors)

Rules flagged 30 items; 27 of them were labeled errors.

| Signal | AUC |
| --- | --- |
| LLM judge severity alone | 0.84 |
| Rules first, then LLM severity | 0.97 |

## Operating table (risk target: ≤ 2 errors per 100 auto-shipped)

| Policy | Auto-ship if | Auto-shipped | Review saved | Errors slipped | Per 100 shipped | Meets target |
| --- | --- | --- | --- | --- | --- | --- |
| LLM only | severity ≤ 1 | 134 | 67% | 9/42 | 6.7 | no |
| LLM only | severity ≤ 2 | 152 | 76% | 13/42 | 8.6 | no |
| LLM only | severity ≤ 3 | 179 | 90% | 23/42 | 12.8 | no |
| LLM only | severity ≤ 4 | 191 | 96% | 33/42 | 17.3 | no |
| LLM only | severity ≤ 5 | 192 | 96% | 34/42 | 17.7 | no |
| Rules + LLM | severity ≤ 1 | 124 | 62% | 0/42 | 0.0 | yes |
| Rules + LLM | severity ≤ 2 | 140 | 70% | 3/42 | 2.1 | no |
| Rules + LLM | severity ≤ 3 | 159 | 80% | 6/42 | 3.8 | no |
| Rules + LLM | severity ≤ 4 | 170 | 85% | 15/42 | 8.8 | no |
| Rules + LLM | severity ≤ 5 | 170 | 85% | 15/42 | 8.8 | no |

Caveat: the punctuation rule was designed after reviewing these labels; confirm the rules + LLM numbers on the next batch before relying on them.