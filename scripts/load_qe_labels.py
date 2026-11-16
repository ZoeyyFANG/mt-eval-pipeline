"""
Load a filled label file into the qe_labels table.

    python scripts/load_qe_labels.py --annotator zoey

Re-running replaces that annotator's earlier labels, so you can label in
chunks and reload any time. Blank rows are skipped.
"""
import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, LABELS_DIR
from common import export_csvs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", required=True)
    a = ap.parse_args()
    key = {r["item_id"]: r for r in csv.DictReader(open(LABELS_DIR / f"_key_{a.annotator}.csv", encoding="utf-8"))}
    rows = list(csv.DictReader(open(LABELS_DIR / f"qe_labels_{a.annotator}.csv", encoding="utf-8-sig")))

    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM qe_labels WHERE annotator = ?", (a.annotator,))
    ts = datetime.now(timezone.utc).isoformat()
    n, bad = 0, []
    for r in rows:
        v = (r.get("has_error") or "").strip()
        if v == "":
            continue
        if v not in ("0", "1"):
            bad.append(r["item_id"])
            continue
        k = key[r["item_id"]]
        con.execute(
            """INSERT INTO qe_labels (string_id, engine, run_id, has_error, error_note, annotator, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (k["string_id"], k["engine"], k["run_id"], int(v), r.get("error_note", ""), a.annotator, ts),
        )
        n += 1
    con.commit()
    export_csvs(con)
    con.close()
    print(f"[labels] loaded {n}/{len(rows)} labels for {a.annotator}"
          + (f"; not 0/1, skipped: {', '.join(bad)}" if bad else ""))


if __name__ == "__main__":
    main()
