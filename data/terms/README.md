# Terminology (Excalidraw EN → zh-CN)

## Method
1. **Corpus**: all 642 strings in Excalidraw `en.json` (not only the 120 in batch 1), so the termbase covers future batches.
2. **Extraction** (`extract_terms.py`): spaCy POS patterns (ADJ/NOUN/PROPN + NOUN/PROPN, up to 3 tokens), kept if they appear in ≥2 strings.
3. **Ranking**: keyness = log2(frequency in Excalidraw / frequency in general English, via `wordfreq`), multiplied by log(1 + number of strings). Domain words (canvas, arrowhead, cardinality) rise; everyday words (file, item) sink.
4. **Output**: 193 candidates → `term_candidates.csv`.
5. **Curation** (manual): merged variants into concepts (stroke / stroke width / stroke style), dropped generic words, added terms extraction missed (verbs like save/paste, single-string features like zen mode), and wrote one concept-oriented entry per meaning (ISO 704): definition from Excalidraw usage, example string key, zh, notes, do-not-translate flag, forbidden translation.
6. **Result**: 69 entries → `termbase.csv`, also exported to TBX (`csv_to_tbx.py`) for TMS import.

## Status
All entries are `proposed` until the linguist (Zoey) reviews them and sets `status=approved`.
Approved terms are imported into the Crowdin glossary and injected into the MT prompt (language assets as prompt data).

## Decisions log
| Term | Decision | Why |
|---|---|---|
| sloppiness, frame, library, library item, zen mode, crow's foot, scene, canvas, drawing | Approved as proposed (潦草度, 画框, 素材库, 素材, 禅模式, 鸦脚, 场景, 画布, 绘图) | Reviewed by Zoey, 2026-11-19 |
| library, frame, element, group, diagram, hand tool, selection | Keep termbase; reference revised to match | Translator consistently used 资料库 / 框架 / 对象 / 组合 / 图表 / 手形工具 / 所选对象. Termbase wins so the reference and the MT glossary agree; 21 strings revised (see data/handoff/review_changes.csv) |

| selection | Marked ambiguous (2026-11-23): tool name 选择 vs selected content 选中内容; no longer a hard rule check | Found in TMS review: toolBar.selection / toolBar.lasso were tool names. Changed after the held-out test, so it applies from the next batch on |

## Reference translation review (batch 1)
- Returned file: `data/handoff/batch1_returned.csv` (kept unchanged as the translator's original).
- Reviewer changes: `data/handoff/review_changes.csv`: 23 strings (21 terminology, 2 missing `{{shortcut_2}}` placeholders).
- After review: placeholders 120/120 OK, term adherence 88/88.
