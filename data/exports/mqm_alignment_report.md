# MQM: human annotation vs machine scores

Framework: docs/mqm_framework.md. 320 segments (batch 1 + held-out batches 2-4). 

## System level: MQM score per engine (penalty points per 1000 source words)

| Engine | Segments | Source words | Minor | Major | Critical | Penalty / 1000 w | Quality score | Verdict | Judge-implied score |
|---|---|---|---|---|---|---|---|---|---|
| claude | 105 | 741 | 17 | 5 | 1 | 90 | 91.0 | FAIL | 97.3 |
| deepl | 107 | 735 | 2 | 7 | 10 | 390 | 61.0 | FAIL | 72.9 |
| google | 108 | 684 | 12 | 10 | 11 | 493 | 50.7 | FAIL | 62.4 |

- Ranking by human MQM: claude > deepl > google; by judge-implied MQM: claude > deepl > google.
- Pass rule (project): no Critical and score >= 95. Raw MT of UI strings is not expected to pass; the score is for comparing engines and tracking change, the verdict shows how far raw MT is from shippable.

Errors by MQM dimension:

| Dimension | claude | deepl | google |
|---|---|---|---|
| Accuracy | 1 | 8 | 8 |
| Design and markup | 0 | 9 | 9 |
| Linguistic conventions | 20 | 0 | 0 |
| Style | 2 | 2 | 5 |
| Terminology | 0 | 0 | 11 |

Systematic errors (same dimension >= 3 times for one engine; fix once at the source):

- claude: Linguistic conventions x20
- deepl: Accuracy x8
- deepl: Design and markup x9
- google: Accuracy x8
- google: Design and markup x9
- google: Style x5
- google: Terminology x11

## Segment level: does the metric order segments like the human does?

| Metric | n | Spearman vs worst human severity | 95% CI |
|---|---|---|---|
| judge | 320 | 0.60 | 0.49 to 0.69 |
| comet (negated) | 200 | 0.45 | 0.34 to 0.55 |
| cometkiwi (negated) | 320 | 0.03 | -0.07 to 0.14 |

## On the human-annotated errors

- 73 segments with errors. Judge (mapped to MQM) gave the same severity on 32 (44%); called 23 of them no error (they would auto-ship without the rule checks).
- Human severity → judge severity (count): critical → critical: 16; critical → minor: 4; major → major: 3; major → minor: 14; major → none: 5; minor → minor: 13; minor → none: 18

Caveats: one human annotator; the judge is Claude scoring Claude among others (self-preference risk); COMET uses references reviewed against the termbase.
