"""
Manual step — deliberately NOT part of the CI pipeline. Human LQA is
your periodic calibration check, not something that should re-run on
every commit. Fill in templates/human_lqa_template.csv by hand (pull
your sample from data/exports/master_view.csv), then run this to load
your scores into the database on the same string_id/engine keys as
the LLM judge, so the two are directly comparable.
"""
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "human_lqa_template.csv"


def main():
    con = sqlite3.connect(DB_PATH)
    ts = datetime.now(timezone.utc).isoformat()
    n = 0
    with open(TEMPLATE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("severity"):
                continue  # skip rows you haven't filled in yet
            con.execute(
                """INSERT INTO human_lqa (string_id, engine, error_type, severity, evaluator, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row["string_id"], row["engine"], row["error_type"],
                    int(row["severity"]), row.get("evaluator") or "zoey", ts,
                ),
            )
            n += 1
    con.commit()
    con.close()
    print(f"[human_lqa] loaded {n} rows from {TEMPLATE.name}")


if __name__ == "__main__":
    main()
