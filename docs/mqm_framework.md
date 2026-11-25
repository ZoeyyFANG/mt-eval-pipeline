# MQM framework for this project (EN → zh-CN, Excalidraw UI)

How human translation quality is measured here: which errors exist, how bad each one is,
and how errors become a score. Based on **MQM-Core** (Multidimensional Quality Metrics,
themqm.org) and the MQM Council's scoring model (Lommel et al., 2024,
arXiv:2405.16969). Adapted for short software UI strings; every adaptation is marked *(project rule)*.

Used by: human LQA (`labels/mqm_annotation_todo.csv`), the MQM alignment analysis
(`scripts/mqm_alignment.py`), and as the reference the LLM judge is compared against.

## 1. Error typology (MQM-Core, 7 dimensions)

Annotate the **dimension › subtype**. Subtypes listed are the ones that occur in UI strings;
other MQM-Core subtypes may be used if needed.

| Dimension | Subtype | Use when | Example from this project |
|---|---|---|---|
| Terminology | wrong term | a termbase term is translated differently | library → 库 (termbase: 素材库) |
| Terminology | DNT violated | a do-not-translate name/key is translated | Mermaid → 美人鱼; Cmd → 命令 |
| Accuracy | mistranslation | wrong meaning or wrong sense for this UI element | Thin (stroke width) → 薄; Sign up → 报名; Wrap (box selection) → 换行 |
| Accuracy | omission / addition | content dropped or added | |
| Accuracy | untranslated | English left where Chinese is expected | |
| Linguistic conventions | grammar | ungrammatical | |
| Linguistic conventions | punctuation | half-width , ? ! : inside Chinese text *(project rule: punctuation sits here, not under Locale conventions)* | 发现问题?提交 |
| Style | unidiomatic | correct but unnatural for a UI label | Gray → 灰色的; 以Mermaid视角查看 |
| Style | register | violates the style guide's register | *(project rule: 您 vs 你 is **Neutral** until the engines are given the style guide)* |
| Locale conventions | number / date / measurement format | wrong format for zh-CN | |
| Audience appropriateness | culture-specific reference | idiom or reference that doesn't land | Hold your horses |
| Design and markup | markup / placeholder | `{{…}}` or `<tag>` translated, dropped, re-cased, broken | {{shortcut}} → {{快捷键}}; <link> → <LINK> |
| Design and markup | length / truncation | likely too long for the UI element | |

Rules
- One error = one annotation. A segment can have several; count each *(project rule: max 2 per segment, the two most severe, so a garbled string does not dominate the score)*.
- **Every occurrence counts** *(project rule, v2)*. MQM's repeated-error practice (count the first,
  mark repeats Neutral) is meant for one translator's document, where a systematic error is fixed
  once. Here each UI string is shown to users on its own, and each engine is a separate "translation",
  so a repeat still reaches users and still costs the engine. Systematic errors (the same
  dimension › subtype three or more times for one engine) are **reported separately** in
  `mqm_alignment_report.md` instead, because they are cheap to fix at the source (glossary,
  DNT list, placeholder protection).
- Judge the target against the source and the key's context, not against a reference translation.

## 2. Severity levels (MQM default multipliers)

| Severity | Penalty | MQM definition | In a UI string, this means |
|---|---|---|---|
| Neutral | 0 | preferential change, or not the translator's fault | 您 vs 你; a different but correct word |
| Minor | 1 | limited impact on usability, understandability or reliability | half-width comma; 灰色的 for Gray; slightly unnatural label |
| Major | 5 | seriously affects understandability, reliability or usability, or is in a highly visible place | wrong sense on a button or option (薄 for Thin, 换行 for Wrap); termbase term on a main feature; any Minor error in a high-visibility string |
| Critical | 25 | content unfit for purpose; serious financial, legal, reputational risk | placeholder broken so raw code shows or the app breaks; instruction that makes the user do the wrong thing; DNT key translated so the shortcut can't be found |

Decision rules *(project rules)*
- **Visibility bumps one level**: Minor → Major in welcome screen, upgrade / pricing / sign-up strings and toolbar tool names (tier 3–4 in `data/tiers.csv`).
- **Placeholders**: translated or dropped `{{…}}` = Critical (renders wrong at runtime). Re-cased tag (`<LINK>`) = Critical unless the engineer confirms the parser is case-insensitive.
- **Terminology**: Minor if the meaning survives (库 vs 素材库), Major if the user could look for the wrong feature.
- When unsure between two levels, choose the lower one and write why in `note`.

## 3. Scoring

Evaluation Word Count (EWC) = English source words in the sample. Reference Word Count (RWC) = 1000.

```
Absolute Penalty Total (APT)  = Σ (Minor × 1 + Major × 5 + Critical × 25)     (all error-type weights = 1)
Normed Penalty Total   (NPT)  = APT × 1000 / EWC                              penalty points per 1000 source words
Raw quality score             = 100 − NPT / 10                                (= 100 − penalty points per 100 words)
```

Pass / fail *(project rule, UI strings)*
- **Fail** if any Critical error, or raw quality score < **95**.
- 95 corresponds to 50 penalty points per 1000 words, e.g. ten Major errors per 1000 words of UI text.
- Calibrated scoring (MQM Council linear model) is not used yet: it needs a stakeholder-agreed
  passing interval. Revisit when there is a client threshold.

Report per engine and per content tier, never only one total: UI strings are short, so one
Critical in a 3-word string moves a small sample a lot.

## 4. Mapping to the LLM judge's 1–6 scale

The judge (`scripts/05_llm_judge.py`) scores task impact 1–6. For comparison only:

| Judge | 1–2 | 3–4 | 5 | 6 |
|---|---|---|---|---|
| MQM | no error / Neutral | Minor | Major | Critical |

The judge is not an MQM annotator: it gives one score per segment and no dimension count,
so system-level MQM scores come from human annotations only.

## 5. Process

1. Annotator reads `labels/GUIDELINES.md` (has_error yes/no) and this framework.
2. Error rows from the QE labelling are annotated with dimension › subtype › severity
   (`scripts/export_mqm_sheet.py` pre-fills the dimension from the error tag; the annotator confirms).
3. A second annotator annotates 20% of error rows; agreement reported as exact severity match
   and Cohen's kappa on severity. Disagreements are resolved against this document, and the
   document is updated when a rule was missing (as with the size-label rule in GUIDELINES.md).
4. `scripts/mqm_alignment.py` computes MQM scores per engine and compares them with the LLM
   judge, COMET and CometKiwi.

Changes to this framework are dated below so earlier scores can be read against the rules
that produced them.

| Date | Change |
|---|---|
| 2026-11-24 | First version. |
| 2026-11-24 | v2: repeated-error rule removed (it was applied across engines, which zeroed one engine's errors because another made them first); systematic errors reported separately. 19 annotations updated: labels/mqm_annotation_corrections.csv. |
