"""
Routing evaluation: LLM judge alone vs deterministic rules + LLM judge.

    python scripts/analyze_routing.py --annotator zoey --risk-target 2

Rules (any one sends the item to human review, whatever the LLM says):
  - placeholder/markup token check (token_ok)
  - glossary term adherence (a termbase term not translated as specified)
  - zh-CN half-width punctuation (locale_check)
Then items the rules pass are auto-shipped if LLM severity <= threshold.

Caveat: the punctuation rule was added after looking at batch-1 labels, so
batch-1 numbers for "rules + LLM" are optimistic. Validate on a later batch.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, EXPORT_DIR
from common import locale_check
from terms import term_adherence
from sklearn.metrics import roc_auc_score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", default="zoey")
    ap.add_argument("--held-out", action="store_true",
                    help="labels come from batches the rules were NOT designed on")
    ap.add_argument("--risk-target", type=float, default=2.0, help="max errors per 100 auto-shipped items")
    a = ap.parse_args()
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT q.string_id, q.engine, q.has_error, j.severity, m.mt_text, m.token_ok, s.source_text
        FROM qe_labels q
        JOIN llm_judge_scores j ON j.string_id = q.string_id AND j.engine = q.engine
        JOIN mt_outputs m ON m.string_id = q.string_id AND m.engine = q.engine
        JOIN source_strings s ON s.string_id = q.string_id
        WHERE q.annotator = ?
          AND j.id IN (SELECT MAX(id) FROM llm_judge_scores GROUP BY string_id, engine)
          AND m.id IN (SELECT MAX(id) FROM mt_outputs GROUP BY string_id, engine)""",
        (a.annotator,)).fetchall()
    if not rows:
        sys.exit("no labeled items found; run load_qe_labels.py first")

    def rule_flags(r):
        sid, _, _, _, mt, tok, src = r
        flags = []
        if not tok:
            flags.append("placeholder")
        if term_adherence(src, mt, sid)["term_detail"]:
            flags.append("terminology")
        if not locale_check(mt)["locale_ok"]:
            flags.append("punctuation")
        return flags

    n, n_err = len(rows), sum(r[2] for r in rows)
    flagged = [r for r in rows if rule_flags(r)]
    y = [r[2] for r in rows]
    auc_llm = roc_auc_score(y, [r[3] for r in rows])
    auc_comb = roc_auc_score(y, [r[3] + (10 if rule_flags(r) else 0) for r in rows])

    out = [f"# Routing evaluation ({a.annotator}, {n} labeled items, {n_err} errors)", "",
           f"Rules flagged {len(flagged)} items; {sum(r[2] for r in flagged)} of them were labeled errors.", "",
           "| Signal | AUC |", "| --- | --- |",
           f"| LLM judge severity alone | {auc_llm:.2f} |",
           f"| Rules first, then LLM severity | {auc_comb:.2f} |", "",
           f"## Operating table (risk target: ≤ {a.risk_target:g} errors per 100 auto-shipped)", "",
           "| Policy | Auto-ship if | Auto-shipped | Review saved | Errors slipped | Per 100 shipped | Meets target |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for label, use_rules in (("LLM only", False), ("Rules + LLM", True)):
        for t in range(1, 6):
            ship = [r for r in rows if r[3] <= t and not (use_rules and rule_flags(r))]
            slip = sum(r[2] for r in ship)
            per100 = 100 * slip / len(ship) if ship else 0
            out.append(f"| {label} | severity ≤ {t} | {len(ship)} | {100 * len(ship) / n:.0f}% | {slip}/{n_err} | "
                       f"{per100:.1f} | {'yes' if ship and per100 <= a.risk_target else 'no'} |")
    if a.held_out:
        out += ["", "Held-out check: the rules were frozen (git commit) before these batches were "
                "translated or labeled."]
    else:
        out += ["", "Caveat: the punctuation rule was designed after reviewing these labels; "
                "confirm the rules + LLM numbers on a held-out batch before relying on them."]
    report = "\n".join(out)
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / f"routing_report_{a.annotator}.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
