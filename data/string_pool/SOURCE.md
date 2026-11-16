# Source strings

**Project:** Excalidraw (open-source whiteboard app) — MIT License, © 2020 Excalidraw
**File:** `packages/excalidraw/locales/en.json`
**Pinned commit:** `dd2f8fc32b92cbf56f4abee6a0cf3b14681b4b55` (pulled 2026-11-03)

642 strings in the original file (nested keys flattened to `a.b.c`). 180 sampled
with a fixed seed (20261103), stratified so the set tests different failure modes:

| Stratum | n | What it stresses |
|---|---|---|
| short (≤2 words) | 50 | ambiguity without context: "Line", "Submit", "Editor" |
| medium (3–14 words) | 52 | everyday UI text |
| placeholder_markup | 32 | `{{count}}`, `{{shortcut}}`, `<link>…</link>` must survive |
| error | 22 | errors / alerts / toasts — tone and clarity |
| long (≥15 words) | 18 | sentence-level fluency, truncation risk |
| colors | 3 | short closed-class terms |
| dnt (keys.*) | 3 | do-not-translate: Ctrl, Esc… |

`tags` in the worksheet is computed per string, so a "medium" string can still carry
`placeholder`.

**Batches** (simulated releases): batch 1 = 120 strings (now in `locales/en.json`),
batches 2–4 = 20 each, every batch mixed across strata. Add them later with
`python scripts/add_batch.py 2` etc.

**Note:** Excalidraw has a community zh-CN translation (Crowdin). Don't look at it
before writing your own references — it would anchor them. Afterwards it can be
added as a fourth "engine" (community human translation) for comparison.
