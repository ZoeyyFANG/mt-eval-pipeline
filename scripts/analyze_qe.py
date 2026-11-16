"""
Evaluate the QE itself against human labels (ROC method).

    python scripts/analyze_qe.py                      # annotator zoey
    python scripts/analyze_qe.py --risk-target 2 --second peer

For each QE signal: how well it separates "contains an error" from
"acceptable" (ROC AUC with a stratified-bootstrap 95% CI), per stratum
where both classes have enough items, and an operating table: if every
item at or below a threshold skips full review, how much review is
saved and how many errors per 100 unreviewed items slip through.

Method after Garland & Berger (2026), "ROC Analysis for Evaluating
Translation Quality Estimation Systems" (arXiv:2605.24721).
Note: AUC here says how well a QE separates good from bad output.
It is NOT a ranking of the MT engines.
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, cohen_kappa_score

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, EXPORT_DIR

# (column, label, higher_means_error, live?)
SIGNALS = [
    ("llm_severity", "LLM judge severity (QE)", True, True),
    ("cometkiwi", "CometKiwi (QE)", False, True),
    ("comet", "COMET (needs reference; validation only)", False, False),
    ("chrf", "chrF++ (needs reference; validation only)", False, False),
]
MIN_PER_CLASS = 5        # below this, no AUC is reported for a stratum
RECOMMENDED = 50         # per class, per Garland & Berger


def load(con, annotator):
    q = """SELECT ql.string_id, ql.engine, ql.has_error, s.stratum, m.token_ok,
                  lj.severity AS llm_severity, cs.cometkiwi, cs.comet, am.chrf
           FROM qe_labels ql
           JOIN source_strings s ON s.string_id = ql.string_id
           JOIN mt_outputs m ON m.string_id = ql.string_id AND m.engine = ql.engine AND m.run_id = ql.run_id
           LEFT JOIN llm_judge_scores lj ON lj.string_id = ql.string_id AND lj.engine = ql.engine AND lj.run_id = ql.run_id
           LEFT JOIN comet_scores cs ON cs.string_id = ql.string_id AND cs.engine = ql.engine AND cs.run_id = ql.run_id
           LEFT JOIN auto_metrics am ON am.string_id = ql.string_id AND am.engine = ql.engine AND am.run_id = ql.run_id
           WHERE ql.annotator = ?"""
    cur = con.execute(q, (annotator,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def auc_ci(y, s, rng, b=1000):
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    auc = roc_auc_score(y, s)
    pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
    boots = []
    for _ in range(b):  # stratified bootstrap: resample each class separately
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        boots.append(roc_auc_score(y[idx], s[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return auc, lo, hi


def oriented(rows, col, higher_is_error):
    keep = [r for r in rows if r[col] is not None]
    y = [r["has_error"] for r in keep]
    s = [r[col] if higher_is_error else -r[col] for r in keep]
    return keep, y, s


def operating_table(y, s, raw_scores, higher_is_error):
    """Items scoring 'safer' than the threshold skip full review."""
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    out = []
    for t in sorted(set(s)):
        skip = s <= t                      # predicted acceptable -> spot-check only
        n_skip = int(skip.sum())
        missed = int((y[skip] == 1).sum())
        out.append({
            "threshold_raw": t if higher_is_error else -t,
            "share_skipping_review": n_skip / len(y),
            "errors_per_100_unreviewed": 100 * missed / n_skip if n_skip else 0.0,
            "errors_caught": int((y[~skip] == 1).sum()) / max(1, int((y == 1).sum())),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", default="zoey")
    ap.add_argument("--second", help="second annotator, for agreement")
    ap.add_argument("--risk-target", type=float, default=2.0,
                    help="max errors per 100 items that skip full review")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    con = sqlite3.connect(DB_PATH)
    rows = load(con, a.annotator)
    lines = [f"# QE evaluation report ({a.annotator}, {len(rows)} labeled items)", ""]
    if not rows:
        sys.exit("No labels loaded yet — run export_label_sample.py, label, then load_qe_labels.py.")

    pos = sum(r["has_error"] for r in rows)
    neg = len(rows) - pos
    lines.append(f"Errors: {pos} · acceptable: {neg}.")
    if min(pos, neg) < RECOMMENDED:
        lines.append(f"**Warning:** fewer than {RECOMMENDED} items in a class; treat AUCs as provisional.")
    lines.append("")

    # 1. label reliability
    if a.second:
        other = {(r["string_id"], r["engine"]): r["has_error"] for r in load(con, a.second)}
        pairs = [(r["has_error"], other[(r["string_id"], r["engine"])])
                 for r in rows if (r["string_id"], r["engine"]) in other]
        if pairs:
            x1, x2 = zip(*pairs)
            agree = np.mean(np.array(x1) == np.array(x2))
            kappa = cohen_kappa_score(x1, x2)
            lines += ["## Label reliability", "",
                      f"{len(pairs)} items labeled by both: agreement {agree:.0%}, Cohen's kappa {kappa:.2f}.", ""]

    # 2. separability, overall and by stratum
    lines += ["## Separability (ROC AUC, 95% CI)", "",
              "| Signal | Live? | n | AUC | 95% CI |", "| --- | --- | --- | --- | --- |"]
    by_stratum_lines = ["", "## AUC by stratum", "",
                        "| Signal | Stratum | errors / acceptable | AUC |", "| --- | --- | --- | --- |"]
    op_rows = []
    for col, label, hi_err, live in SIGNALS:
        keep, y, s = oriented(rows, col, hi_err)
        if len(set(y)) < 2:
            continue
        auc, lo, hi = auc_ci(y, s, rng)
        lines.append(f"| {label} | {'yes' if live else 'no'} | {len(y)} | {auc:.2f} | {lo:.2f}–{hi:.2f} |")
        for st in sorted({r["stratum"] for r in keep}):
            sub = [(yy, ss) for r, yy, ss in zip(keep, y, s) if r["stratum"] == st]
            yp = sum(v for v, _ in sub)
            yn = len(sub) - yp
            if yp >= MIN_PER_CLASS and yn >= MIN_PER_CLASS:
                st_auc = f"{roc_auc_score([v for v, _ in sub], [w for _, w in sub]):.2f}"
            else:
                st_auc = "too few"
            by_stratum_lines.append(f"| {label} | {st} | {yp} / {yn} | {st_auc} |")
        if live:
            for row in operating_table(y, s, None, hi_err):
                op_rows.append({"signal": col, **row})
    lines += by_stratum_lines

    # 3. operating points against the risk target
    lines += ["", f"## Operating point (risk target: ≤ {a.risk_target:g} errors per 100 unreviewed)", ""]
    for col, label, _, live in SIGNALS:
        cand = [r for r in op_rows if r["signal"] == col
                and r["errors_per_100_unreviewed"] <= a.risk_target and r["share_skipping_review"] > 0]
        if not live or not any(r["signal"] == col for r in op_rows):
            continue
        if cand:
            best = max(cand, key=lambda r: r["share_skipping_review"])
            lines.append(f"- {label}: skip full review when score is "
                         f"{'≤' if col == 'llm_severity' else '≥'} {best['threshold_raw']:.3g} → "
                         f"{best['share_skipping_review']:.0%} of items skip review, "
                         f"{best['errors_per_100_unreviewed']:.1f} errors per 100 of them.")
        else:
            lines.append(f"- {label}: no threshold meets the risk target; everything needs review.")

    # 4. the deterministic token check, for comparison
    tok_bad = [r for r in rows if r["token_ok"] == 0]
    if tok_bad:
        caught = sum(r["has_error"] for r in tok_bad)
        lines += ["", f"Rule-based token check flagged {len(tok_bad)} labeled items; "
                      f"{caught} of them were labeled as errors."]

    out = Path(EXPORT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "qe_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import csv
    with open(out / "qe_operating_table.csv", "w", newline="", encoding="utf-8-sig") as f:
        if op_rows:
            w = csv.DictWriter(f, fieldnames=list(op_rows[0]))
            w.writeheader()
            w.writerows(op_rows)
    print("\n".join(lines))
    print(f"\n[qe] report written to {out / 'qe_report.md'}")


if __name__ == "__main__":
    main()
