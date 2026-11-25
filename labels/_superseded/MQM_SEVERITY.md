# MQM severity pass (error rows only)

Every row here was already labelled `has_error = 1`. Give it one number: how much
does this error hurt **the user doing the task in the UI**? Same 1–6 scale as the
LLM judge (`scripts/05_llm_judge.py`), so human and machine scores sit on one ruler.

| Severity | Meaning | Typical example |
|---|---|---|
| 3 | Minor: cosmetic, user understands and completes the task | half-width comma inside Chinese; 灰色的 for Gray |
| 4 | Noticeable: user may hesitate or misread, task still completable | 库 instead of 素材库; slightly wrong sense in a tooltip |
| 5 | Major: likely to cause a wrong action or confusion | Sign up → 报名; Saving (status) → 保存 |
| 6 | Critical: breaks function or gives a wrong instruction | `{{shortcut}}` → `{{快捷键}}` (renders raw); tag dropped |

Rules
- Judge the error, not the engine (engine names are hidden).
- `error_type` is pre-filled from your note's first tag. Fix it if it's wrong; types:
  accuracy, terminology, fluency, locale_convention, placeholder_mismatch, truncation_risk, style.
- One row, one severity: if a row has two errors, score the worse one and mention the other in `error_note`.
- Placeholder and markup errors are 6 when the string would break or show raw code; 5 if it only
  looks wrong (e.g. `<LINK>` re-cased but still works — check with the engineer view if unsure).
- Aim for ~15 seconds a row. Save as `labels/mqm_severity.csv` (UTF-8).

How it's used: rows with `has_error = 0` count as no error. Per segment, human severity
(1 for no error, else this number) is compared with the LLM judge's severity and with COMET
(`scripts/mqm_alignment.py`): segment-level correlation, and whether human MQM and the judge
rank the three engines the same way.
