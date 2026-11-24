"""
Analyse the non-inferiority ratings exactly as pre-registered in docs/non_inferiority_protocol.md.

    python3 scripts/noninf_analysis.py

Primary: share of strings with >= 1 major/critical error, pipeline (P) minus human-only (H),
paired bootstrap 95% CI; non-inferior if the upper bound < MARGIN.
Secondary: MQM penalty per 1,000 source words (minor 1, major 5, critical 25).
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LABELS_DIR, EXPORT_DIR

MARGIN = 0.05            # fixed in the protocol: do not change after seeing data
WEIGHTS = {"minor": 1, "major": 5, "critical": 25}
B, SEED = 10000, 20261124


def n(v):
    return int(v) if str(v).strip() else 0


def main():
    key = {r["item_id"]: r for r in csv.DictReader(open(LABELS_DIR / "_key_noninf.csv", encoding="utf-8"))}
    ratings = list(csv.DictReader(open(LABELS_DIR / "noninf_ratings.csv", encoding="utf-8-sig")))
    blank = [r["item_id"] for r in ratings if not any(str(r[k]).strip() for k in WEIGHTS)]
    if len(blank) == len(ratings):
        sys.exit("no ratings yet")
    per = {}
    for r in ratings:
        k = key[r["item_id"]]
        per.setdefault(k["string_id"], {"words": int(k["words"] or 0)})[k["version"]] = {
            "bad": int(n(r["major"]) + n(r["critical"]) > 0),
            "penalty": sum(WEIGHTS[s] * n(r[s]) for s in WEIGHTS)}
    sids = [s for s, v in per.items() if "P" in v and "H" in v]
    P = np.array([per[s]["P"]["bad"] for s in sids]); H = np.array([per[s]["H"]["bad"] for s in sids])
    pen_P = np.array([per[s]["P"]["penalty"] for s in sids]); pen_H = np.array([per[s]["H"]["penalty"] for s in sids])
    words = np.array([per[s]["words"] for s in sids])
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(sids), (B, len(sids)))
    diff = (P[idx].mean(1) - H[idx].mean(1))
    lo, hi = np.percentile(diff, [2.5, 97.5])
    mqm = lambda pen, i=None: 1000 * (pen[i].sum(1) if i is not None else pen.sum()) / (words[i].sum(1) if i is not None else words.sum())
    mdiff = mqm(pen_P, idx) - mqm(pen_H, idx)
    mlo, mhi = np.percentile(mdiff, [2.5, 97.5])
    verdict = ("NON-INFERIOR" if hi < MARGIN else
               "INFERIOR" if lo > MARGIN else "INCONCLUSIVE")
    out = [f"# Non-inferiority result ({len(sids)} strings, {words.sum()} source words)", "",
           f"Pre-registered margin: {MARGIN * 100:.0f} percentage points on the share of strings with a major/critical error.", "",
           "| Version | Strings with major/critical error | MQM penalty per 1,000 words |", "| --- | --- | --- |",
           f"| Pipeline | {P.sum()}/{len(sids)} ({100 * P.mean():.1f}%) | {mqm(pen_P):.1f} |",
           f"| Human-only (TEP) | {H.sum()}/{len(sids)} ({100 * H.mean():.1f}%) | {mqm(pen_H):.1f} |", "",
           f"- Difference P − H: {100 * (P.mean() - H.mean()):+.1f} pp, 95% CI {100 * lo:+.1f} to {100 * hi:+.1f} pp",
           f"- MQM penalty difference: {mqm(pen_P) - mqm(pen_H):+.1f}, 95% CI {mlo:+.1f} to {mhi:+.1f}",
           f"- **Verdict: {verdict}** (non-inferior if the upper bound is below +{MARGIN * 100:.0f} pp)"]
    if blank:
        out.append(f"- Note: {len(blank)} items had no error counts and were read as error-free.")
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / "noninferiority_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
