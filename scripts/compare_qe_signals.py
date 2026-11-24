"""
Compare the two reference-free QE signals: LLM judge severity vs CometKiwi.

    python3 scripts/compare_qe_signals.py --annotators zoey,zoey_b2

Reports AUC overall, per stratum, on the items the deterministic rules let
through (the only items a QE score actually decides in routing), whether
combining the two helps, and how much CometKiwi tracks string length.
Writes data/exports/qe_signals_report.md.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, EXPORT_DIR
from common import locale_check
from terms import term_adherence


def auc(y, s):
    return f"{roc_auc_score(y, s):.2f}" if 0 < sum(y) < len(y) else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotators", default="zoey,zoey_b2")
    a = ap.parse_args()
    names = [x.strip() for x in a.annotators.split(",")]
    con = sqlite3.connect(DB_PATH)
    q = f"""SELECT q.string_id, q.engine, q.has_error, cs.cometkiwi, j.severity, s.stratum,
                   LENGTH(s.source_text), m.mt_text, m.token_ok, s.source_text
            FROM qe_labels q
            JOIN comet_scores cs ON cs.string_id = q.string_id AND cs.engine = q.engine
            JOIN llm_judge_scores j ON j.string_id = q.string_id AND j.engine = q.engine
            JOIN mt_outputs m ON m.string_id = q.string_id AND m.engine = q.engine
            JOIN source_strings s ON s.string_id = q.string_id
            WHERE q.annotator IN ({",".join("?" * len(names))}) AND cs.cometkiwi IS NOT NULL
              AND j.id IN (SELECT MAX(id) FROM llm_judge_scores GROUP BY string_id, engine)
              AND m.id IN (SELECT MAX(id) FROM mt_outputs GROUP BY string_id, engine)"""
    rows = con.execute(q, names).fetchall()
    if not rows:
        sys.exit("no rows: run comet_scores.py and load_qe_labels.py first")
    y = [r[2] for r in rows]
    kiwi = [-r[3] for r in rows]          # higher CometKiwi = better, so negate
    llm = [r[4] for r in rows]

    def flagged(r):
        sid, _, _, _, _, _, _, mt, tok, src = r
        return (not tok) or bool(term_adherence(src, mt, sid)["term_detail"]) or not locale_check(mt)["locale_ok"]

    passed = [r for r in rows if not flagged(r)]
    yp = [r[2] for r in passed]
    comb = rankdata([r[4] for r in passed]) + rankdata([-r[3] for r in passed])
    rho_len = spearmanr([r[3] for r in rows], [r[6] for r in rows])[0]

    out = [f"# QE signals: LLM judge vs CometKiwi ({', '.join(names)}; {len(rows)} labeled items, {sum(y)} errors)", "",
           "| Items | n | errors | LLM judge AUC | CometKiwi AUC |", "| --- | --- | --- | --- | --- |",
           f"| All labeled | {len(rows)} | {sum(y)} | {auc(y, llm)} | {auc(y, kiwi)} |",
           f"| Passed the rule checks | {len(passed)} | {sum(yp)} | {auc(yp, [r[4] for r in passed])} | "
           f"{auc(yp, [-r[3] for r in passed])} |"]
    for st in sorted({r[5] for r in rows}):
        sub = [r for r in rows if r[5] == st]
        ys = [r[2] for r in sub]
        out.append(f"| Stratum: {st} | {len(sub)} | {sum(ys)} | {auc(ys, [r[4] for r in sub])} | "
                   f"{auc(ys, [-r[3] for r in sub])} |")
    out += ["",
            f"- LLM + CometKiwi combined (rank average) on rule-passed items: AUC {auc(yp, comb)}",
            f"- CometKiwi vs source length: Spearman rho = {rho_len:.2f} (short strings get lower scores regardless of quality)",
            f"- Mean CometKiwi: error {np.mean([r[3] for r in rows if r[2]]):.3f} vs acceptable "
            f"{np.mean([r[3] for r in rows if not r[2]]):.3f}"]
    report = "\n".join(out)
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / "qe_signals_report.md").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
