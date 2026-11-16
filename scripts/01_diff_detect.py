"""
Step 1: Diff detection.

Compares the current locale file against the last-processed snapshot
to find new or changed source strings. Only these get pushed through
the rest of the pipeline — this is what makes it an incremental
pipeline instead of re-scoring (and re-billing) everything every run.
"""
import json
import hashlib
import sqlite3
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LOCALE_FILE, SNAPSHOT_FILE, PENDING_FILE, DB_PATH


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def string_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def already_in_db(string_id, text_hash):
    """Extra safety net: even if the snapshot file is out of sync
    (e.g. someone deleted it), never re-score something already
    scored for this exact text — that's what actually protects your
    API budget from an accidental re-run."""
    if not Path(DB_PATH).exists():
        return False
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        "SELECT 1 FROM source_strings WHERE string_id = ? AND text_hash = ?",
        (string_id, text_hash),
    )
    found = cur.fetchone() is not None
    con.close()
    return found


def main():
    current = load_json(LOCALE_FILE, {})
    snapshot = load_json(SNAPSHOT_FILE, {})

    pending = []
    for string_id, source_text in current.items():
        text_hash = string_hash(source_text)
        prev_hash = snapshot.get(string_id, {}).get("text_hash")
        if text_hash == prev_hash:
            continue  # unchanged since last run
        if already_in_db(string_id, text_hash):
            continue  # defensive dedupe
        pending.append({
            "string_id": string_id,
            "source_text": source_text,
            "text_hash": text_hash,
            "change_type": "new" if string_id not in snapshot else "changed",
        })

    Path(PENDING_FILE).write_text(
        json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[diff] {len(pending)} new/changed strings out of {len(current)} total.")


if __name__ == "__main__":
    main()
