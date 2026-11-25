# Does generated context fix errors? (blind labels)

| Engine | Without context: errors / n | With context: errors / n | Fixed | Broken |
|---|---|---|---|---|
| claude | 6 / 25 | 5 / 25 | 3 | 2 |
| deepl | 10 / 25 | 2 / 25 | 8 | 0 |

Targets were chosen because they had errors, so the no-context error rate is high by design; read Fixed vs Broken, not the absolute rates. The no-context rows are re-labelled here, blind, next to the new ones, so both conditions are judged in the same sitting.

## Reading (2026-11-24)

- Labels: Zoey, blind. 3 rows corrected for internal contradiction (note said the translation should be X, and it was X): data/context/context_ab_corrections.csv.
- DeepL (context passed via the API `context` parameter): 8 fixed, 0 broken. Fixes are meaning-level: Thin 薄→细, Saving 保存→正在保存, "go to" 参加→访问, Enter 输入→Enter, {{快捷键}}→{{shortcut}}, binding/快捷键 confusion.
- Claude: meaning-level fixes only for Sharp (锐利→尖角) and Enter. The other ins and outs are half-width punctuation (, ?) appearing or disappearing between two runs: run-to-run noise, not an effect of context, and caught by the post-MT punctuation rule anyway.
- Context notes: generated from code usage + PR, reviewed with AI assistance against the code (data/context/context_review.csv, column `reviewer`).
