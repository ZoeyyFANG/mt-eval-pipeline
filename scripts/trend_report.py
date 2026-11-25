"""
Quality over time, one row per replayed batch (db/replay.db).

    python scripts/trend_report.py                # trend.csv + trend_report.md
    python scripts/trend_report.py --audit-sample # also: labels/audit_replay_todo.csv

What a localization team watches release over release:
  - volume: how many strings landed (new vs changed)
  - source gate: share held for context / review before MT
  - engines: mean judge severity, share flagged (sev >= 3), placeholder
    failures, term adherence -- per engine, so a silent drop shows up
  - routing: share auto-shipped (spot_check) vs sent to people
  - audit: a human checks a few auto-shipped strings per batch; the
    observed error rate is compared with the 2-per-100 risk target.
    The auto-ship rule is only trustworthy while the audit agrees.
"""
import argparse, csv, os, random, sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = os.environ.get("MT_EVAL_REPLAY_NAME", "replay")
DB = ROOT / "db" / f"{NAME}.db"
OUT = ROOT / "data" / NAME / "exports"
AUDIT_TODO = ROOT / "labels" / "audit_replay_todo.csv"
AUDIT_DONE = ROOT / "labels" / "audit_replay.csv"   # same file, has_error filled in by a person
AUDIT_KEY = ROOT / "labels" / "_key_audit_replay.csv"  # which engine produced each row (kept apart)
ENGINES = ["google", "deepl", "claude"]
HUMAN = {"full_review", "repair", "mandatory_review", "human_only", "human_translation", "transcreation"}
AUDIT_N = 10
RISK_TARGET = 2.0   # errors per 100 auto-shipped strings


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def wilson(e, n, z=1.96):
    p = e / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / d
    return 100 * max(0, c - h), 100 * (c + h)


def batch_rows(con):
    rows = []
    for run_id, label, date, n_new, n_chg, n_proc in con.execute(
            "SELECT run_id, label, batch_date, n_new, n_changed, n_processed FROM replay_batches WHERE done = 1 ORDER BY batch_date"):
        r = {"batch": label, "date": date, "new": n_new, "changed": n_chg, "processed": n_proc}
        gate = Counter(g for (g,) in con.execute("SELECT gate_label FROM source_gate_results WHERE run_id = ?", (run_id,)))
        ng = sum(gate.values())
        r["gate_auto_approve_%"] = pct(gate["auto_approve"], ng)
        r["gate_needs_context_%"] = pct(gate["needs_context"], ng)
        r["gate_needs_review_%"] = pct(gate["needs_review"], ng)
        for e in ENGINES:
            sev = [s for (s,) in con.execute(
                "SELECT severity FROM llm_judge_scores WHERE run_id = ? AND engine = ?", (run_id, e)) if s is not None]
            r[f"{e}_mean_sev"] = round(sum(sev) / len(sev), 2) if sev else None
            r[f"{e}_flagged_%"] = pct(sum(s >= 3 for s in sev), len(sev))
            tok = [t for (t,) in con.execute("SELECT token_ok FROM mt_outputs WHERE run_id = ? AND engine = ?", (run_id, e))]
            r[f"{e}_placeholder_fail_%"] = pct(sum(t == 0 for t in tok), len(tok))
            th, tt = con.execute("SELECT SUM(term_hits), SUM(term_total) FROM mt_outputs WHERE run_id = ? AND engine = ?",
                                 (run_id, e)).fetchone()
            r[f"{e}_term_adherence_%"] = pct(th or 0, tt) if tt else None
        routes = Counter(x for (x,) in con.execute("SELECT route FROM batch_routes WHERE run_id = ?", (run_id,)))
        nr = sum(routes.values())
        r["auto_ship_%"] = pct(routes["spot_check"], nr)
        r["to_people_%"] = pct(sum(v for k, v in routes.items() if k in HUMAN), nr)
        r["routes"] = "; ".join(f"{k} {v}" for k, v in routes.most_common())
        picked = Counter(x for (x,) in con.execute(
            "SELECT engine FROM batch_routes WHERE run_id = ? AND engine IS NOT NULL", (run_id,)))
        r["picked_engine"] = "; ".join(f"{k} {v}" for k, v in picked.most_common())
        rows.append((run_id, r))
    return rows


def audit(con, rows, make_sample):
    done = {}
    if AUDIT_DONE.exists():
        for a in csv.DictReader(open(AUDIT_DONE, encoding="utf-8-sig")):
            if a.get("has_error", "").strip() in ("0", "1"):
                done.setdefault(a["batch"], []).append(int(a["has_error"]))
    for run_id, r in rows:
        lab = done.get(r["batch"], [])
        r["audit_n"] = len(lab)
        r["audit_errors_per_100"] = pct(sum(lab), len(lab)) if lab else None
    if make_sample:
        rng, out = random.Random(20261124), []
        for run_id, r in rows:
            # source text AS IT WAS in this batch: source_strings holds the latest text, and a
            # string changed in a later quarter would pair today's English with an old translation
            import json
            as_of = json.loads((ROOT / "data" / "replay" / "points" / f"{r['batch']}.json").read_text(encoding="utf-8"))
            shipped = [(sid, as_of.get(sid, ""), eng, mt) for sid, eng, mt in con.execute(
                """SELECT string_id, engine, mt_text FROM batch_routes
                   WHERE run_id = ? AND route = 'spot_check' ORDER BY string_id""", (run_id,))]
            for sid, src, eng, mt in rng.sample(shipped, min(AUDIT_N, len(shipped))):
                # engine hidden on purpose: the auditor judges the text, not the brand
                out.append({"batch": r["batch"], "string_id": sid, "source_en": src, "mt_zh": mt,
                            "has_error": "", "note": "", "_engine": eng})
        AUDIT_TODO.parent.mkdir(exist_ok=True)
        with open(AUDIT_TODO, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["batch", "string_id", "source_en", "mt_zh", "has_error", "note"])
            w.writeheader(); w.writerows({k: v for k, v in o.items() if k != "_engine"} for o in out)
        with open(AUDIT_KEY, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["batch", "string_id", "engine"])
            w.writeheader(); w.writerows({"batch": o["batch"], "string_id": o["string_id"], "engine": o["_engine"]} for o in out)
        print(f"[trend] audit sample: {len(out)} auto-shipped strings -> {AUDIT_TODO.relative_to(ROOT)}")


def write(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    data = [r for _, r in rows]
    with open(OUT / "trend.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    cols = ["batch", "date", "new", "changed", "gate_needs_context_%", "claude_mean_sev", "deepl_mean_sev",
            "google_mean_sev", "auto_ship_%", "to_people_%", "audit_n", "audit_errors_per_100"]
    md = ["# Quality over time (Excalidraw history replay)", "",
          "One row per quarter of real Excalidraw string changes, scored with today's engines.",
          "Content drift only: engine drift is tracked from now on with the fixed regression set.", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |" for r in data]
    lab = [r for r in data if r["audit_n"]]
    if lab:
        n = sum(r["audit_n"] for r in lab)
        e = sum(round(r["audit_errors_per_100"] * r["audit_n"] / 100) for r in lab)
        md += ["", f"Audit pooled: {e} errors in {n} auto-shipped strings = {pct(e, n)} per 100 "
                   f"(target <= {RISK_TARGET}). Per-batch audits are small (<= {AUDIT_N}); read the pooled number.",
               f"95% Wilson interval: {wilson(e, n)[0]:.1f} to {wilson(e, n)[1]:.1f} per 100. "
               + ("Consistent with the target but too small to prove it (about 150 error-free audits would)."
                  if wilson(e, n)[0] <= RISK_TARGET else "Above the target even at the low end: review the auto-ship rule.")]
    (OUT / "trend_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-sample", action="store_true")
    args = ap.parse_args()
    if not DB.exists():
        raise SystemExit(f"{DB} not found — run scripts/replay_history.py first")
    con = sqlite3.connect(DB)
    rows = batch_rows(con)
    if not rows:
        raise SystemExit("no finished batches yet")
    audit(con, rows, args.audit_sample)
    write(rows)


if __name__ == "__main__":
    main()
