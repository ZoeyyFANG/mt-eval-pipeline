"""
Turn the binary QE labels into an MQM annotation sheet (one row per error segment).

Framework: docs/mqm_framework.md (MQM-Core dimensions, Neutral/Minor/Major/Critical).
Rows labelled has_error=0 already have their MQM answer: no error, no penalty.
Only error rows need annotating, and the dimension/subtype is pre-filled from the
tag the annotator wrote in error_note. The annotator confirms or fixes it and sets
the severity; a second error per segment is optional.

    python scripts/export_mqm_sheet.py   ->  labels/mqm_annotation_todo.csv
Fill `severity` (minor / major / critical / neutral), save as labels/mqm_annotation.csv.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "labels"
TAG2MQM = {"accuracy": ("Accuracy", "mistranslation"),
           "terminology": ("Terminology", "wrong term"),
           "placeholder": ("Design and markup", "markup / placeholder"),
           "fluency": ("Style", "unidiomatic"),
           "locale": ("Linguistic conventions", "punctuation"),
           "untranslated": ("Accuracy", "untranslated")}
SETS = [("b1", "qe_labels_zoey.csv"), ("b2", "qe_labels_zoey_b2.csv")]
COLS = ["row_id", "context_key", "source_en", "mt_zh", "error_note", "dimension", "subtype", "severity",
        "error2_dimension", "error2_subtype", "error2_severity", "note"]


def main():
    out = []
    for tag, fname in SETS:
        for r in csv.DictReader(open(LAB / fname, encoding="utf-8-sig")):
            if r["has_error"].strip() != "1":
                continue
            first = (r["error_note"] or "").strip().split(" ")[0].lower().rstrip(":,\uff1a")
            dim, sub = TAG2MQM.get(first, ("", ""))
            out.append({"row_id": f"{tag}-{r['item_id']}", "context_key": r["context_key"],
                        "source_en": r["source_en"], "mt_zh": r["mt_zh"], "error_note": r["error_note"],
                        "dimension": dim, "subtype": sub, "severity": "",
                        "error2_dimension": "", "error2_subtype": "", "error2_severity": "", "note": ""})
    with open(LAB / "mqm_annotation_todo.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out)
    print(f"[mqm] {len(out)} error rows -> labels/mqm_annotation_todo.csv "
          f"({sum(not o['dimension'] for o in out)} without a dimension guess). Rules: docs/mqm_framework.md")


if __name__ == "__main__":
    main()
