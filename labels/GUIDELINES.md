# QE labeling guidelines (EN → zh-CN, Excalidraw UI)

**Question for every row:** *Could this translation ship to users as it is?*
- `has_error = 0`: yes, ship it (even if you would phrase it differently).
- `has_error = 1`: no, a reviewer would have to change it before release.

When `has_error = 1`, write a short reason in `error_note` using one of these tags first:
`accuracy`, `terminology`, `placeholder`, `fluency`, `locale`, `untranslated`, plus a few words.

## What counts as an error (label 1)

| Tag | Rule | Example (source → MT) |
|---|---|---|
| accuracy | Wrong meaning, wrong sense for the UI, missing or added content | Sign up → 报名; Storage → 贮存; Thin (stroke width) → 薄; Saving (status) → 保存 |
| terminology | A term in `data/terms/termbase.csv` translated differently, or a do-not-translate name translated | library → 库 / 资料库; Edit Mermaid manually → 手动编辑美人鱼 |
| placeholder | `{{…}}`, `<tag>…</tag>` changed, translated, dropped, re-cased | {{shortcut}} → {{快捷键}}; <link> → <LINK>; {{shortcut}} dropped |
| fluency | Ungrammatical or clearly unnatural for a UI label | Gray → 灰色的; Large → 大的; Total → 全部的 |
| locale | Wrong Chinese punctuation that users will see: half-width `,` `?` inside Chinese text | …发布,简而言之,… |
| untranslated | English left where it should be Chinese | |

Keyboard keys are **not** translated: Cmd → Cmd is correct, Cmd → 命令 is an error; Enter (key) → 进入/输入 is an error.

## What does NOT count (label 0)

- **您 vs 你.** Our style guide prefers 你, but the engines were not told this. Do not count it; it is measured separately.
- A different but correct word choice (最近使用 vs 最近使用过, 青色 vs 蓝绿色 for Teal).
- Spacing between Chinese and Latin text (按{{shortcut}} vs 按 {{shortcut}}).
- A full stop added or dropped at the end (您现有的内容将被保留。).
- Single-character size labels in a size picker (Small / Medium / Large → 小 / 中 / 大). Added 2026-11-23 after an annotator disagreement.

## How to work

1. Read `context_key` first: it tells you where the string appears (`toolBar` = toolbar, `keys` = keyboard key, `errors`/`alerts` = messages, `labels` = buttons/menus, `colors` = colour names, `hints` = on-canvas tips).
2. Read the English, then the Chinese. Decide in 20–30 seconds. First instinct is fine.
3. Unsure? Ask: "Would a user be confused, or would a reviewer fix this before release?" Yes → 1.
4. Do not look at `_key_zoey.csv` (engine names) or any scores until all 200 rows are done.
5. Label in order; take breaks every ~50 rows. Do not go back and change earlier labels unless you made a slip.
6. Keep the file as CSV (UTF-8) when saving from Excel.

## Second annotator

A second person labels the first 50 items with these same guidelines (`--from zoey`), without seeing the first annotator's labels. We report Cohen's kappa between the two.

## Agreement (batch 1)

Second annotator labeled items q001–q050 independently: Cohen's kappa = 0.75 against the first annotator's original labels (46/50 agree).
Disagreements were adjudicated (see `label_corrections.csv`); the rule on single-character size labels above came out of this step.
