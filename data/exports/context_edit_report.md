# Generated translator context: how much did the reviewer change?

25 notes generated from code usage + commit/PR. Reviewed by: claude (AI-assisted, checked against Excalidraw code at dd2f8fc), pending Zoey approval.

| Outcome | Notes | Share |
|---|---|---|
| unchanged | 17 | 68% |
| formatting_only | 0 | 0% |
| trimmed_only | 0 | 0% |
| meaning | 8 | 32% |

- Mean character edit distance (all edits): 0.20
- Mean word edit distance (meaning edits only): 0.24
- Formatting-only and trimmed-only edits can be automated away (style rules, a length cap in the prompt);
  meaning edits (words added or changed) mean the evidence or the model was wrong: those are the ones that matter.

## Meaning edits

- `colors.transparent` word distance 0.52: Removed "not see-through glass": transparent here does mean see-through, so that contrast was wrong.
- `welcomeScreen.app.center_heading_plus` word distance 0.78: Added why it is shown (signed-in Plus user on the free app) and that the name is a link: code splits on the exact text.
- `keys.cmd` word distance 0.88: Fixed "replacing Ctrl/Cmd": on macOS Cmd replaces Ctrl (shortcut.ts).
- `labels.signUp` word distance 0.60: Added the sense to avoid; this is the string that was mistranslated as enrolling.
- `progressDialog.title` word distance 1.00: Generated note stated it as a dialog title; code search finds no usage. Flag as possibly unused string.
- `toast.copyStyles` word distance 0.81: Trimmed; replaced "not clothing" with what styles are.
- `helpDialog.deepBoxSelect` word distance 0.83: Rewrote: generated note was muddled about "box"; behaviour taken from the shortcut list and PR #4502.
- `helpDialog.github` word distance 0.66: Added where the link goes (github.com/excalidraw/excalidraw/issues) and that Submit = report a bug.
