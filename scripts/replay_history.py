"""
Replay Excalidraw's real string history through the pipeline, one
quarter at a time (points from scripts/replay_prepare.py).

    python scripts/replay_history.py            # every batch not yet done
    python scripts/replay_history.py --mock     # dry run, fake API calls, separate DB

Per batch: write that quarter's en.json -> 01 diff -> 02 gate -> 03 MT ->
04 metrics -> 05 judge -> 06 write DB -> 08 route. The repair agent (09)
and the Crowdin push are skipped: this is measurement, not delivery.

Everything goes to a sandbox (db/replay.db, data/replay/): the main DB,
its routes and what is in Crowdin are never touched. Human QE labels are
copied in so 08 ranks engines the same way the main run does.
Re-running is safe: finished batches are skipped, a batch that failed
half-way resumes where it stopped.
"""
import argparse, csv, hashlib, json, os, sqlite3, subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
POINTS = ROOT / "data" / "replay" / "points"
STEPS_SCORE = ["01_diff_detect.py", "02_source_gate.py", "03_run_mt_engines.py",
               "04_auto_metrics.py", "05_llm_judge.py", "06_write_db.py"]


def run(step, env):
    print(f"\n=== {step} ===", flush=True)
    if subprocess.run([sys.executable, str(SCRIPTS / step)], env=env).returncode != 0:
        sys.exit(f"[replay] {step} failed. Fix it and run this script again; it resumes here.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fake API calls, writes to replay_mock")
    args = ap.parse_args()

    env = dict(os.environ, MT_EVAL_REPLAY="1")
    if args.mock:
        env.update(MT_EVAL_MOCK="1", MT_EVAL_REPLAY_NAME="replay_mock")
    name = env.get("MT_EVAL_REPLAY_NAME", "replay")
    sandbox, db_path = ROOT / "data" / name, ROOT / "db" / f"{name}.db"
    sandbox.mkdir(parents=True, exist_ok=True)

    points = list(csv.DictReader(open(ROOT / "data" / "replay" / "points.csv", encoding="utf-8")))
    if not points:
        sys.exit("[replay] no points — run scripts/replay_prepare.py first")
    baseline, batches = points[0], points[1:]

    con = sqlite3.connect(db_path)
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS replay_batches (
            run_id TEXT PRIMARY KEY, label TEXT, batch_date TEXT, commit_sha TEXT,
            n_new INTEGER, n_changed INTEGER, n_processed INTEGER, done INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS batch_routes (   -- routing decision as made when the batch landed
            run_id TEXT, string_id TEXT, route TEXT, engine TEXT, mt_text TEXT,
            severity INTEGER, tier INTEGER, rule_flags TEXT, reason TEXT);""")
    main_db = ROOT / "db" / "pipeline.db"
    no_labels = con.execute("SELECT COUNT(*) FROM qe_labels").fetchone()[0] == 0
    if no_labels and main_db.exists():   # read-only copy; the main DB is never written
        con.execute("ATTACH DATABASE ? AS main_db", (str(main_db),))
        con.execute("INSERT INTO qe_labels SELECT * FROM main_db.qe_labels")
        con.commit(); con.execute("DETACH DATABASE main_db")
        print(f"[replay] copied {con.execute('SELECT COUNT(*) FROM qe_labels').fetchone()[0]} human QE labels for engine ranking")
    con.commit()

    snap = sandbox / "last_processed_en.json"
    if not snap.exists():   # the baseline release counts as already localized
        base = json.loads((POINTS / f"{baseline['label']}.json").read_text(encoding="utf-8"))
        snap.write_text(json.dumps({k: {"text_hash": hashlib.sha256(v.encode()).hexdigest()[:12],
                                        "last_run_id": "baseline"} for k, v in base.items()},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[replay] baseline {baseline['label']} ({baseline['total']} strings) marked as localized")

    for b in batches:
        run_id = f"replay_{b['label']}"
        row = con.execute("SELECT done FROM replay_batches WHERE run_id = ?", (run_id,)).fetchone()
        if row and row[0]:
            print(f"[replay] {b['label']} already done, skipping"); continue
        print(f"\n########## {b['label']} ({b['date']}): {b['new']} new, {b['changed']} changed ##########")
        benv = dict(env, MT_EVAL_RUN_ID=run_id, MT_EVAL_RUN_TS=b["date"])
        if not con.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone():
            (sandbox / "en.json").write_text(
                (POINTS / f"{b['label']}.json").read_text(encoding="utf-8"), encoding="utf-8")
            for step in STEPS_SCORE:
                run(step, benv)
                if step == "01_diff_detect.py" and not json.loads(
                        (sandbox / "_pending_batch.json").read_text(encoding="utf-8")):
                    print("[replay] nothing new in this batch"); break
        con.close()
        run("08_route.py", benv)
        con = sqlite3.connect(db_path)
        ids = [r[0] for r in con.execute("""SELECT string_id FROM mt_outputs WHERE run_id = ?
                                            UNION SELECT string_id FROM source_gate_results WHERE run_id = ?""",
                                         (run_id, run_id))]
        last = con.execute("SELECT MAX(route_run) FROM routes").fetchone()[0]
        con.execute("DELETE FROM batch_routes WHERE run_id = ?", (run_id,))
        if ids:
            q = ",".join("?" * len(ids))
            con.execute(f"""INSERT INTO batch_routes
                SELECT ?, string_id, route, engine, mt_text, severity, tier, rule_flags, reason
                FROM routes WHERE route_run = ? AND string_id IN ({q})""", (run_id, last, *ids))
        con.execute("INSERT OR REPLACE INTO replay_batches VALUES (?,?,?,?,?,?,?,1)",
                    (run_id, b["label"], b["date"], b["commit"], int(b["new"]), int(b["changed"]), len(ids)))
        con.commit()
        print(f"[replay] {b['label']} done: {len(ids)} strings routed")
    con.close()
    print("\n[replay] all batches done. Next: python scripts/trend_report.py")


if __name__ == "__main__":
    main()
