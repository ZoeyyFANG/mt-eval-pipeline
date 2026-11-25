"""
Step 6: Persist everything under this run's run_id, update the
snapshot so step 1 treats these strings as processed next time, and
export flat CSVs for Excel / Power BI to read.

run_id = timestamp + short commit sha. That pairing is what lets
Power BI plot "severity over time" instead of just "severity by
engine".
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    DB_PATH, SCHEMA_FILE, SNAPSHOT_FILE, PENDING_FILE, GATE_RESULTS_FILE,
    MT_OUTPUTS_FILE, AUTO_METRICS_FILE, LLM_JUDGE_FILE, MOCK, ENGINES,
)
from common import load_strata, extract_tokens, export_csvs


def get_run_id():
    if os.environ.get("MT_EVAL_RUN_ID"):  # replay: one run per historical batch
        return os.environ["MT_EVAL_RUN_ID"]
    commit_sha = os.environ.get("GITHUB_SHA", "mock" if MOCK else "local")[:7]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{commit_sha}"


def ensure_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(Path(SCHEMA_FILE).read_text(encoding="utf-8"))
    return con


def load(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def main():
    run_id = get_run_id()
    ts = os.environ.get("MT_EVAL_RUN_TS") or datetime.now(timezone.utc).isoformat()
    trigger = ("replay" if os.environ.get("MT_EVAL_RUN_ID") else
               "mock" if MOCK else ("ci" if os.environ.get("GITHUB_SHA") else "local"))
    strata = load_strata()

    con = ensure_db()
    con.execute(
        "INSERT INTO runs (run_id, commit_sha, timestamp, trigger_type) VALUES (?, ?, ?, ?)",
        (run_id, os.environ.get("GITHUB_SHA", trigger), ts, trigger),
    )

    pending = load(PENDING_FILE, [])
    for item in pending:
        meta = strata.get(item["string_id"], {})
        con.execute(
            """INSERT INTO source_strings
               (string_id, source_text, text_hash, stratum, tags, batch, has_placeholder, first_seen_run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(string_id) DO UPDATE SET
                 source_text = excluded.source_text, text_hash = excluded.text_hash""",
            (item["string_id"], item["source_text"], item["text_hash"],
             meta.get("stratum"), meta.get("tags"),
             int(meta["batch"]) if meta.get("batch") else None,
             int(bool(extract_tokens(item["source_text"]))), run_id),
        )

    for g in load(GATE_RESULTS_FILE, []):
        con.execute(
            "INSERT INTO source_gate_results (string_id, run_id, gate_label, reason) VALUES (?, ?, ?, ?)",
            (g["string_id"], run_id, g["gate_label"], g.get("reason")),
        )

    # every MT output is stored, whether or not a reference exists yet
    for m in load(MT_OUTPUTS_FILE, []):
        con.execute(
            """INSERT INTO mt_outputs (string_id, engine, run_id, mt_text, token_ok, token_detail,
                                       glossary_used, term_total, term_hits, term_detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (m["string_id"], m["engine"], run_id, m["mt_text"],
             int(m.get("token_ok", True)), m.get("token_detail", ""),
             m.get("glossary_used", 0), m.get("term_total", 0), m.get("term_hits", 0),
             m.get("term_detail", "")),
        )

    for m in load(AUTO_METRICS_FILE, []):
        con.execute(
            "INSERT INTO auto_metrics (string_id, engine, run_id, bleu, chrf, ter) VALUES (?, ?, ?, ?, ?, ?)",
            (m["string_id"], m["engine"], run_id, m["bleu"], m["chrf"], m["ter"]),
        )

    for j in load(LLM_JUDGE_FILE, []):
        con.execute(
            """INSERT INTO llm_judge_scores (string_id, engine, run_id, error_type, severity, rationale)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (j["string_id"], j["engine"], run_id, j["error_type"], j["severity"], j.get("rationale")),
        )
    con.commit()

    # Only mark a string as processed if this run actually handled it: it got at
    # least one MT output, or a WORKING gate deliberately held it for review.
    # A failed API call must never hide a string from the next run.
    # every engine must have produced output; a string missing one engine is
    # retried next run instead of entering the comparison incomplete
    engines_per = {}
    for m in load(MT_OUTPUTS_FILE, []):
        engines_per.setdefault(m["string_id"], set()).add(m["engine"])
    translated = {sid for sid, es in engines_per.items() if set(ENGINES) <= es}
    held = {g["string_id"] for g in load(GATE_RESULTS_FILE, [])
            if g["gate_label"] == "needs_review" and not str(g.get("reason", "")).startswith("gate call failed")}
    snapshot = load(SNAPSHOT_FILE, {})
    skipped = 0
    for item in pending:
        if item["string_id"] in translated or item["string_id"] in held:
            snapshot[item["string_id"]] = {"text_hash": item["text_hash"], "last_run_id": run_id}
        else:
            skipped += 1
    if skipped:
        print(f"[db] {skipped} strings not marked as processed (API failures) — they will be retried next run.")
    Path(SNAPSHOT_FILE).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    export_csvs(con)
    con.close()
    print(f"[db] run {run_id} written: {len(pending)} strings processed.")


if __name__ == "__main__":
    main()
