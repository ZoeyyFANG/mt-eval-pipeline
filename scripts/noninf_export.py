"""
Build the blind rating sheet for the non-inferiority test (docs/non_inferiority_protocol.md).

    python3 scripts/noninf_export.py

Pipeline version: the approved Crowdin text pulled by crowdin_pull_review.py (review_edits).
Human-only version: data/handoff/noninf_human_batch5_done.csv (string_id, zh_translation).
Writes labels/noninf_ratings.csv (what the rater sees: A/B per string in random order)
and labels/_key_noninf.csv (which letter is which version; do not show the rater).
"""
import csv
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, LABELS_DIR, ROOT

HUMAN = ROOT / "data" / "handoff" / "noninf_human_batch5_done.csv"


def main():
    ws = [r for r in csv.DictReader(open(ROOT / "data" / "reference_worksheet.csv", encoding="utf-8-sig"))
          if r["batch"] == "5"]
    human = {r["string_id"]: r["zh_translation"] for r in csv.DictReader(open(HUMAN, encoding="utf-8-sig"))}
    con = sqlite3.connect(DB_PATH)
    pipe = dict(con.execute("""SELECT string_id, final_text FROM review_edits
                               WHERE id IN (SELECT MAX(id) FROM review_edits GROUP BY string_id)"""))
    missing = [r["string_id"] for r in ws if not pipe.get(r["string_id"]) or not human.get(r["string_id"])]
    if missing:
        sys.exit(f"{len(missing)} strings lack a pipeline or human version, e.g. {missing[:5]}")
    out = LABELS_DIR / "noninf_ratings.csv"
    if out.exists():
        sys.exit(f"{out} exists: rename it first so ratings are never overwritten")
    rng = random.Random(20261124)
    rows, key = [], []
    for i, r in enumerate(ws, 1):
        pair = [("P", pipe[r["string_id"]]), ("H", human[r["string_id"]])]
        rng.shuffle(pair)
        for letter, (version, zh) in zip("AB", pair):
            item = f"n{i:03d}{letter}"
            rows.append({"item_id": item, "context_key": r["string_id"], "source_en": r["source_en"],
                         "translation": zh, "minor": "", "major": "", "critical": "", "note": ""})
            key.append({"item_id": item, "string_id": r["string_id"], "version": version,
                        "words": r["word_count"]})
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(LABELS_DIR / "_key_noninf.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(key[0])); w.writeheader(); w.writerows(key)
    print(f"[noninf] {len(rows)} items for {len(ws)} strings -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
