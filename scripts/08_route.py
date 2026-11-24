"""
Step 8: give every string exactly one route. Rules decide; the LLM only scores.

    python3 scripts/08_route.py

For each string, the latest candidates from every engine are checked:
  1. keys.* (keyboard keys)            -> dnt_check       (source text, no MT)
  2. source gate said needs_review     -> human_only      (nothing pushed)
  3. pick the best candidate: rule checks pass first, then lowest LLM severity,
     then the engine with the lowest human-labeled error rate (from qe_labels)
  4. best candidate fails a rule       -> mandatory_review
  5. severity >= REPAIR_MIN_SEVERITY   -> repair          (agent, then review)
  6. severity <= SPOT_CHECK_MAX        -> spot_check      (10% sampled review)
  7. otherwise                         -> full_review

Writes the routes table and data/exports/routes.csv.
"""
import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, SCHEMA_FILE, EXPORT_DIR, SPOT_CHECK_MAX_SEVERITY, REPAIR_MIN_SEVERITY
from common import locale_check
from terms import term_adherence


def engine_preference(con):
    """Engines ordered by human-labeled error rate; falls back to mean LLM severity."""
    rows = con.execute("""SELECT engine, AVG(has_error), COUNT(*) FROM qe_labels
                          GROUP BY engine HAVING COUNT(*) >= 20""").fetchall()
    if rows:
        return [e for e, _, _ in sorted(rows, key=lambda r: r[1])], "human-labeled error rate"
    rows = con.execute("SELECT engine, AVG(severity) FROM llm_judge_scores GROUP BY engine").fetchall()
    return [e for e, _ in sorted(rows, key=lambda r: r[1])], "mean LLM severity"


def rule_flags(string_id, source, mt, token_ok):
    flags = []
    if not token_ok:
        flags.append("placeholder")
    t = term_adherence(source, mt, string_id)
    if t["term_detail"]:
        flags.append("terminology(" + t["term_detail"] + ")")
    loc = locale_check(mt)
    if not loc["locale_ok"]:
        flags.append("punctuation(" + loc["locale_detail"] + ")")
    return flags


def main():
    con = sqlite3.connect(DB_PATH)
    con.executescript(Path(SCHEMA_FILE).read_text(encoding="utf-8"))
    prefer, basis = engine_preference(con)
    rank = {e: i for i, e in enumerate(prefer)}

    strings = con.execute("SELECT string_id, source_text FROM source_strings").fetchall()
    gate = dict(con.execute("""SELECT string_id, gate_label FROM source_gate_results
                               WHERE id IN (SELECT MAX(id) FROM source_gate_results GROUP BY string_id)"""))
    cands = {}
    for sid, eng, mt, tok, sev in con.execute("""
            SELECT m.string_id, m.engine, m.mt_text, m.token_ok, j.severity
            FROM mt_outputs m
            LEFT JOIN llm_judge_scores j ON j.string_id = m.string_id AND j.engine = m.engine
                 AND j.id IN (SELECT MAX(id) FROM llm_judge_scores GROUP BY string_id, engine)
            WHERE m.id IN (SELECT MAX(id) FROM mt_outputs GROUP BY string_id, engine)"""):
        cands.setdefault(sid, []).append((eng, mt, tok, sev if sev is not None else 6))

    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = []
    for sid, source in strings:
        if sid.startswith("keys."):
            out.append((sid, "dnt_check", None, source, None, "", "keyboard key: ship as printed"))
            continue
        if gate.get(sid) == "needs_review" or sid not in cands:
            out.append((sid, "human_only", None, None, None, "", "source gate: needs_review / no MT"))
            continue
        scored = []
        for eng, mt, tok, sev in cands[sid]:
            flags = rule_flags(sid, source, mt, tok)
            scored.append((bool(flags), sev, rank.get(eng, 99), eng, mt, flags))
        scored.sort()
        failed, sev, _, eng, mt, flags = scored[0]
        if failed:
            route, why = "mandatory_review", "every candidate fails a rule check"
        elif sev >= REPAIR_MIN_SEVERITY:
            route, why = "repair", f"best severity {sev} >= {REPAIR_MIN_SEVERITY}"
        elif sev <= SPOT_CHECK_MAX_SEVERITY:
            route, why = "spot_check", f"rules pass, severity {sev} <= {SPOT_CHECK_MAX_SEVERITY}"
        else:
            route, why = "full_review", f"rules pass, severity {sev}"
        out.append((sid, route, eng, mt, sev, "; ".join(flags), why))

    con.executemany("""INSERT INTO routes (string_id, route_run, route, engine, mt_text, severity, rule_flags, reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(o[0], run, *o[1:]) for o in out])
    con.commit()

    EXPORT_DIR.mkdir(exist_ok=True)
    with open(EXPORT_DIR / "routes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["string_id", "route", "engine", "mt_text", "severity", "rule_flags", "reason"])
        w.writerows(out)
    from collections import Counter
    c = Counter(o[1] for o in out)
    print(f"[route] engine preference ({basis}): {' > '.join(prefer)}")
    print(f"[route] {len(out)} strings: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"[route] chosen engine: " + ", ".join(f"{k} {v}" for k, v in Counter(o[2] for o in out if o[2]).most_common()))


if __name__ == "__main__":
    main()
