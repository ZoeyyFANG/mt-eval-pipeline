"""
MQM penalty per engine from the human annotation (docs/mqm_framework.md).
Shared by the router (engine preference) and scripts/mqm_alignment.py.
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "labels"
PEN = {"neutral": 0, "minor": 1, "major": 5, "critical": 25}
SETS = [("b1", "qe_labels_zoey.csv", "_key_zoey.csv"), ("b2", "qe_labels_zoey_b2.csv", "_key_zoey_b2.csv")]


def engine_penalty_per_1000(min_segments=20):
    """engine -> (MQM penalty points per 1000 source words, segments). Empty dict if
    the MQM annotation is missing or any error row is still unscored."""
    p = LAB / "mqm_annotation.csv"
    if not p.exists():
        return {}
    pen = {}
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        sevs = [r[c].strip().lower() for c in ("severity", "error2_severity") if r.get(c, "").strip()]
        if not sevs:
            return {}
        pen[r["row_id"]] = sum(PEN[s] for s in sevs)
    words, points, n = defaultdict(int), defaultdict(int), defaultdict(int)
    for tag, lab, key in SETS:
        if not (LAB / lab).exists():
            continue
        keys = {r["item_id"]: r["engine"] for r in csv.DictReader(open(LAB / key, encoding="utf-8-sig"))}
        for r in csv.DictReader(open(LAB / lab, encoding="utf-8-sig")):
            e = keys[r["item_id"]]
            words[e] += max(1, len(r["source_en"].split()))
            points[e] += pen.get(f"{tag}-{r['item_id']}", 0) if r["has_error"].strip() == "1" else 0
            n[e] += 1
    return {e: (points[e] * 1000 / words[e], n[e]) for e in words if n[e] >= min_segments}
