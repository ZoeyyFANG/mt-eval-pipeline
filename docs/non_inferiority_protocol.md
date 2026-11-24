# Non-inferiority test: pipeline vs human-only translation

**Status: designed and pre-registered, not yet run.** This file and the batch-5 sample are
committed to git before any batch-5 string is translated, routed or rated. The commit hash
is the proof that the sample, the margin and the decision rule were fixed before any result
was seen. Nothing below may change once data collection starts; a change means a new,
dated version of this file and a new commit, explained in the report.

## Question
Does the pipeline (MT + rules + LLM routing + repair agent + risk-based human review)
deliver quality that is **not meaningfully worse** than a human-only process
(translate + review, TEP), at about half the cost?

## Strings
Batch 5: **230 Excalidraw strings (913 source words)** never used in this project before:
not in batches 1–4, and not used to set any rule, threshold, tier or termbase decision.
Sampled with a fixed seed (20261124), stratified by what is left in Excalidraw's en.json:
placeholder/markup 18 and error 12 (all that remain), medium 100, short 100.
Files: `data/string_pool/batch_5.json`; worksheet rows with batch 5.

### Why 230
The primary endpoint is a difference of two proportions on the same strings. Assuming a
major-error rate around 8% for both versions (an assumption, not a measured figure), the 95%
interval of the difference is about ±1.96·√(2·0.08·0.92/n). Keeping its half-width at or
below the 5-point margin needs n ≈ 226. A dry run with simulated ratings on 60 strings gave
an interval of about ±10 points, too wide to decide anything.

## The two versions
- **Pipeline (P):** batch 5 run through the pipeline **frozen at this commit** (same code,
  termbase, thresholds, tiers, agent limits). The version that would ship: auto-shipped
  strings as they are; reviewed strings after the TMS review.
- **Human-only (H):** a linguist translates all 230 strings with the same termbase and
  style guide, without MT or AI tools; a second linguist reviews (TEP).

## People (roles, to be filled when the test runs)
| Role | Constraint |
|---|---|
| H translator | not the P reviewer; no MT or AI |
| H reviewer | not the H translator |
| P reviewer (TMS review of routed strings) | not the H translator |
| Rater | authored and reviewed **neither** version |

## Rating
- The rater sees each string twice, A/B in random order per string, with no engine, route or
  version shown (`scripts/noninf_export.py`).
- Errors are annotated MQM-style: number of minor / major / critical errors per translation,
  with a short note. Definitions follow `labels/GUIDELINES.md`: major = a reviewer must fix it
  before release; critical = breaks the function, or misstates a legal or privacy fact.
- Weights (MQM scoring model): minor 1, major 5, critical 25.
- Before rating, the rater calibrates on 10 batch-1 strings (not part of the test).

## Decision rule (fixed now)
- **Primary endpoint:** share of strings with at least one major or critical error.
- **Non-inferiority margin:** 5 percentage points.
- **Verdict** from the 95% paired bootstrap interval of (P − H), 10,000 resamples, seed 20261124:
  - upper bound below +5 pp → **non-inferior**
  - lower bound above +5 pp → **inferior**
  - otherwise → **inconclusive** (reported as such, never as a pass)
- **Secondary (reported, not decisive):** MQM penalty per 1,000 source words for each version
  with its interval; cost per word of each version from `scripts/cost_model.py`; results by stratum.

## Steps when it runs
1. Fill the people table above in a new commit (roles only; no change to the rules).
2. `python3 scripts/add_batch.py 5` → `python3 scripts/run_pipeline.py` → `crowdin_push_mt.py`
   → TMS review → `crowdin_pull_review.py`. The P version is the approved text.
3. H version: `data/handoff/noninf_human_batch5.csv` + `data/handoff/glossary.csv` to the
   translator, then to the reviewer; save as `data/handoff/noninf_human_batch5_done.csv`.
4. `python3 scripts/noninf_export.py` → `labels/noninf_ratings.csv` for the rater.
5. `python3 scripts/noninf_analysis.py` → `data/exports/noninferiority_report.md`.

## Estimated effort
H translation ≈ 913 words, H review ≈ 913 words, rating ≈ 460 translations (about 3–4 hours),
P review of routed strings ≈ 1 hour.
