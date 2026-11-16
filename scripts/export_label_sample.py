"""
Export a blind, stratified sample of MT outputs for binary QE labeling.

    python scripts/export_label_sample.py --annotator zoey --n 200
    python scripts/export_label_sample.py --annotator peer --from zoey --n 50

The annotator file shows only an item_id, the English source and the
Chinese MT: no engine name, no scores, so the label is not anchored by
them. The key (item_id -> string/engine/run) goes to a separate file.
Fill `has_error` with 1 (contains an error: any meaning, terminology,
placeholder or major fluency problem) or 0 (acceptable to ship).
"""
import argparse
import csv
import random
import sqlite3
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, LABELS_DIR

FIELDS = ["item_id", "source_en", "mt_zh", "has_error", "error_note"]


def latest_outputs(con):
    """One row per string x engine: the most recent run."""
    q = """SELECT m.string_id, m.engine, m.run_id, s.stratum, s.source_text, m.mt_text
           FROM mt_outputs m JOIN source_strings s ON s.string_id = m.string_id
           WHERE m.id IN (SELECT MAX(id) FROM mt_outputs GROUP BY string_id, engine)"""
    return [dict(zip(["string_id", "engine", "run_id", "stratum", "source", "mt"], r))
            for r in con.execute(q)]


def stratified(rows, n, rng, floor=10):
    by = defaultdict(list)
    for r in rows:
        by[r["stratum"] or "unknown"].append(r)
    for v in by.values():
        rng.shuffle(v)
    total = len(rows)
    take = {k: min(len(v), max(floor, round(n * len(v) / total))) for k, v in by.items()}
    while sum(take.values()) > n:                      # trim the largest strata first
        k = max(take, key=lambda k: take[k] - floor)
        take[k] -= 1
    picked = [r for k, v in by.items() for r in v[:take[k]]]
    rng.shuffle(picked)
    return picked


def write(annotator, items):
    LABELS_DIR.mkdir(exist_ok=True)
    work = LABELS_DIR / f"qe_labels_{annotator}.csv"
    key = LABELS_DIR / f"_key_{annotator}.csv"
    if work.exists():
        sys.exit(f"{work} already exists — delete or rename it first, so labels are never overwritten.")
    with open(work, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for it in items:
            w.writerow({"item_id": it["item_id"], "source_en": it["source"], "mt_zh": it["mt"],
                        "has_error": "", "error_note": ""})
    with open(key, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "string_id", "engine", "run_id", "stratum"])
        w.writeheader()
        for it in items:
            w.writerow({k: it[k] for k in ["item_id", "string_id", "engine", "run_id", "stratum"]})
    print(f"[labels] wrote {len(items)} items to {work.relative_to(LABELS_DIR.parent)} (key: {key.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261116)
    ap.add_argument("--from", dest="source_annotator",
                    help="copy the first N items of another annotator's sample (for agreement)")
    a = ap.parse_args()

    if a.source_annotator:
        src_key = LABELS_DIR / f"_key_{a.source_annotator}.csv"
        src_work = LABELS_DIR / f"qe_labels_{a.source_annotator}.csv"
        keys = list(csv.DictReader(open(src_key, encoding="utf-8")))[: a.n]
        text = {r["item_id"]: r for r in csv.DictReader(open(src_work, encoding="utf-8-sig"))}
        items = [{**k, "source": text[k["item_id"]]["source_en"], "mt": text[k["item_id"]]["mt_zh"]}
                 for k in keys]
    else:
        con = sqlite3.connect(DB_PATH)
        rows = latest_outputs(con)
        con.close()
        picked = stratified(rows, a.n, random.Random(a.seed))
        items = [{**r, "item_id": f"q{i:03d}"} for i, r in enumerate(picked, 1)]
    write(a.annotator, items)


if __name__ == "__main__":
    main()
