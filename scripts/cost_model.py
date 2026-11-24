"""
Cost model: pipeline cost per word vs a human-only TEP baseline (translate + edit/review).

    python3 scripts/cost_model.py

Rates are inputs (data/cost_rates.csv, USD per source word), never baked into
the code; every scenario row names its source. Volumes come from the latest
routes (source word count per route).

    route               review cost per word
    spot_check          spot_check_share x review   (only the sampled share is reviewed)
    full_review         mtpe
    mandatory_review    mtpe
    repair              mtpe (+ PM time per escalation)
    human_translation   translation + review        (tier 3: TEP)
    transcreation       translation x transcreation_multiplier + review
    dnt_check           0
  + machine cost (MT + QE calls) on every word that gets MT

Savings = 1 - C_pipeline / C_baseline, where the baseline is TEP for every word.
Writes data/exports/cost_report.md and cost_by_route.csv.
"""
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, EXPORT_DIR, ROOT

RATES = ROOT / "data" / "cost_rates.csv"


def words(text):
    # source is English: count word-like tokens, placeholders and tags excluded
    text = re.sub(r"\{\{[^}]*\}\}|<[^>]+>", " ", text or "")
    return len(re.findall(r"[A-Za-z0-9'+]+", text))


def per_word(route, r):
    t, rv, pe = float(r["translation"]), float(r["review"]), float(r["mtpe"])
    return {"spot_check": float(r["spot_check_share"]) * rv, "full_review": pe, "mandatory_review": pe,
            "repair": pe, "human_translation": t + rv,
            "transcreation": t * float(r["transcreation_multiplier"]) + rv,
            "dnt_check": 0.0, "human_only": t + rv}.get(route, t + rv)


def main():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""SELECT r.string_id, r.route, s.source_text FROM routes r
                          JOIN source_strings s ON s.string_id = r.string_id
                          WHERE r.id IN (SELECT MAX(id) FROM routes GROUP BY string_id)""").fetchall()
    esc = con.execute("""SELECT COUNT(*) FROM agent_outcomes WHERE outcome = 'escalated'
                         AND id IN (SELECT MAX(id) FROM agent_outcomes GROUP BY string_id)""").fetchone()[0] \
        if con.execute("SELECT name FROM sqlite_master WHERE name='agent_outcomes'").fetchone() else 0
    vol = defaultdict(lambda: [0, 0])
    for sid, route, src in rows:
        vol[route][0] += 1
        vol[route][1] += words(src)
    total_words = sum(v[1] for v in vol.values())
    mt_words = sum(v[1] for k, v in vol.items() if k not in ("human_translation", "transcreation", "human_only"))

    scen = list(csv.DictReader(open(RATES, encoding="utf-8")))
    out = [f"# Cost model ({len(rows)} strings, {total_words} source words)", "",
           "Rates are inputs from data/cost_rates.csv (USD per source word). " + scen[0]["source"], "",
           "| Route | Strings | Words | Share of words |", "| --- | --- | --- | --- |"]
    for route, (n, w) in sorted(vol.items(), key=lambda x: -x[1][1]):
        out.append(f"| {route} | {n} | {w} | {100 * w / total_words:.0f}% |")
    out += ["", "| Scenario | Baseline TEP | Pipeline | Per word: baseline -> pipeline | Savings |",
            "| --- | --- | --- | --- | --- |"]
    by_route = []
    for r in scen:
        base = total_words * (float(r["translation"]) + float(r["review"]))
        pipe = sum(w * per_word(route, r) for route, (n, w) in vol.items())
        pipe += mt_words * float(r["mt_per_word"]) + esc * float(r["pm_per_escalation"])
        out.append(f"| {r['scenario']} | ${base:,.2f} | ${pipe:,.2f} | ${base / total_words:.3f} -> "
                   f"${pipe / total_words:.3f} | {100 * (1 - pipe / base):.0f}% |")
        for route, (n, w) in vol.items():
            by_route.append((r["scenario"], route, n, w, round(w * per_word(route, r), 2)))
    out += ["", f"Escalations charged PM time: {esc}. MT + QE machine cost applied to {mt_words} words.",
            "Savings depend mostly on the share of words that can be spot-checked, which the QE evaluation "
            "set (rules + LLM, severity <= 2, held-out risk 1.3 errors per 100 shipped)."]
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / "cost_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    with open(EXPORT_DIR / "cost_by_route.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "route", "strings", "words", "cost_usd"])
        w.writerows(by_route)
    print("\n".join(out))


if __name__ == "__main__":
    main()
