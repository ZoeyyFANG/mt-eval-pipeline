# MT Evaluation & Quality Observability Pipeline

**Can a quality-estimation (QE) score be trusted to decide which machine translations skip human review — and how far?**

This project answers that question for EN→ZH software UI strings, and builds the localization workflow around the answer: every new source string is screened, translated by three engines, scored, routed by explicit rules, and reviewed by a human only where risk or value calls for it.

> Status: in progress (November 2026). Pipeline and QE-evaluation tooling are built and tested in mock mode; first real run pending.

## What it does

```
locales/en.json changes (push / weekly / manual)
   │
   ├─ 01 diff detect        only new or changed keys; never re-scores (or re-bills) old ones
   ├─ 02 source gate        LLM screens the source: auto_approve / needs_context / needs_review
   ├─ 03 MT engines         Google, DeepL, Claude + a rule-based placeholder/markup check
   ├─ 04 reference metrics  BLEU, chrF++, TER (validation only: live strings have no reference)
   ├─ 05 LLM judge          reference-free QE: MQM-lite error type + severity 1–6
   └─ 06 database           SQLite with run_id per run; CSV exports for Excel / Power BI

Offline (not in CI)
   comet_scores.py          COMET (with reference) and CometKiwi (reference-free QE)
   export_label_sample.py   blind, stratified sample for binary human labels
   load_qe_labels.py        load labels (one file per annotator)
   analyze_qe.py            ROC/AUC per QE signal with bootstrap CIs, per stratum,
                            inter-annotator agreement, and the review threshold that
                            meets a risk target (errors per 100 unreviewed strings)
```

## Why it is built this way

- **Routing uses only reference-free signals.** In production a new string has no reference translation, so BLEU/COMET cannot route it. They are used offline to cross-check the QE.
- **The QE is evaluated, not assumed.** Following Garland & Berger (2026), *ROC Analysis for Evaluating Translation Quality Estimation Systems* (arXiv:2605.24721): binary human labels, ROC curves, and thresholds chosen against an explicit risk target.
- **Placeholders are checked by rules, not by a model.** A broken `{{count}}` or `<link>` must be caught every time.
- **Humans stay accountable.** The pipeline recommends; thresholds, releases and escalations are owned by people.

## Data

180 UI strings from [Excalidraw](https://github.com/excalidraw/excalidraw) (`packages/excalidraw/locales/en.json`, commit `dd2f8fc`), sampled with a fixed seed and stratified by type: short, medium, placeholder/markup, error, long, colors, do-not-translate. They are released in four batches to simulate continuous localization. See `data/string_pool/SOURCE.md`.

Reference translations are written by hand in `data/reference_worksheet.csv` before looking at Excalidraw's community translation.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env              # add ANTHROPIC_API_KEY, GOOGLE_TRANSLATE_API_KEY, DEEPL_API_KEY

MT_EVAL_MOCK=1 python scripts/run_pipeline.py   # dry run: fake API responses, no keys, no cost
python scripts/run_pipeline.py                  # real run
```

Then, to evaluate the QE:

```bash
python scripts/build_references.py                       # worksheet -> data/references.json
pip install -r requirements-comet.txt                    # optional, ~2 GB
python scripts/comet_scores.py                           # CometKiwi is gated: accept its licence on Hugging Face first
python scripts/export_label_sample.py --annotator zoey --n 200
#   fill has_error (1 = contains an error, 0 = acceptable) in labels/qe_labels_zoey.csv
python scripts/load_qe_labels.py --annotator zoey
python scripts/export_label_sample.py --annotator peer --from zoey --n 50   # second annotator
python scripts/load_qe_labels.py --annotator peer
python scripts/analyze_qe.py --second peer --risk-target 2
```

Release the next batch of strings with `python scripts/add_batch.py 2`, then commit: the GitHub Action runs the pipeline on the new keys.

## GitHub Actions

`.github/workflows/pipeline.yml` runs on a push that changes `locales/en.json`, weekly, or by hand. Add `ANTHROPIC_API_KEY`, `GOOGLE_TRANSLATE_API_KEY` and `DEEPL_API_KEY` under *Settings → Secrets and variables → Actions*. The run commits the database and exports back to the repo.

## Roadmap

1. Baseline run on batch 1 — *in progress*
2. Calibrate: human labels, COMET/CometKiwi, ROC thresholds
3. Router and remediation agent (bounded retries, escalation to a human)
4. Crowdin integration: pre-translation push, reviewer-edit pull-back, automatic PR

## License

Code: MIT, see `LICENSE`. Source strings © 2020 Excalidraw, MIT, see `data/string_pool/EXCALIDRAW_LICENSE`. CometKiwi model weights are CC BY-NC-SA 4.0 and are not distributed here.
