# QE signals: LLM judge vs CometKiwi (zoey, zoey_b2; 320 labeled items, 73 errors)

| Items | n | errors | LLM judge AUC | CometKiwi AUC |
| --- | --- | --- | --- | --- |
| All labeled | 320 | 73 | 0.83 | 0.52 |
| Passed the rule checks | 267 | 24 | 0.93 | 0.70 |
| Stratum: colors | 9 | 3 | 0.83 | 0.83 |
| Stratum: dnt | 9 | 4 | 1.00 | 0.70 |
| Stratum: error | 40 | 7 | 0.75 | 0.52 |
| Stratum: long | 32 | 11 | 0.77 | 0.56 |
| Stratum: medium | 85 | 12 | 0.68 | 0.73 |
| Stratum: placeholder_markup | 57 | 24 | 0.90 | 0.44 |
| Stratum: short | 88 | 12 | 0.88 | 0.49 |

- LLM + CometKiwi combined (rank average) on rule-passed items: AUC 0.91
- CometKiwi vs source length: Spearman rho = 0.41 (short strings get lower scores regardless of quality)
- Mean CometKiwi: error 0.791 vs acceptable 0.798
