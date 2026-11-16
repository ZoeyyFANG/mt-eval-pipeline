"""
Offline: COMET (with reference) and CometKiwi (reference-free QE).

Not part of CI: the models are large and run on CPU in minutes, not
seconds. Run it after a pipeline run, then re-export.

    pip install -r requirements-comet.txt
    huggingface-cli login      # CometKiwi is a gated model: accept its licence on Hugging Face first
    python scripts/comet_scores.py              # latest output per string x engine
    python scripts/comet_scores.py --no-kiwi    # COMET only

Models: Unbabel/wmt22-comet-da (Apache-2.0) and
Unbabel/wmt22-cometkiwi-da (CC BY-NC-SA 4.0, non-commercial use).
"""
import argparse
import json
import sqlite3
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, REFERENCES_FILE
from common import export_csvs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-kiwi", action="store_true")
    ap.add_argument("--batch-size", type=int, default=8)
    a = ap.parse_args()

    from comet import download_model, load_from_checkpoint

    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """SELECT m.string_id, m.engine, m.run_id, s.source_text, m.mt_text
           FROM mt_outputs m JOIN source_strings s ON s.string_id = m.string_id
           WHERE m.id IN (SELECT MAX(id) FROM mt_outputs GROUP BY string_id, engine)"""
    ).fetchall()
    refs = json.loads(Path(REFERENCES_FILE).read_text(encoding="utf-8")) if Path(REFERENCES_FILE).exists() else {}

    comet = {}
    with_ref = [r for r in rows if refs.get(r[0])]
    if with_ref:
        model = load_from_checkpoint(download_model("Unbabel/wmt22-comet-da"))
        data = [{"src": r[3], "mt": r[4], "ref": refs[r[0]]} for r in with_ref]
        scores = model.predict(data, batch_size=a.batch_size, gpus=0).scores
        comet = {(r[0], r[1], r[2]): sc for r, sc in zip(with_ref, scores)}
        print(f"[comet] scored {len(comet)} outputs with references")

    kiwi = {}
    if not a.no_kiwi:
        model = load_from_checkpoint(download_model("Unbabel/wmt22-cometkiwi-da"))
        data = [{"src": r[3], "mt": r[4]} for r in rows]
        scores = model.predict(data, batch_size=a.batch_size, gpus=0).scores
        kiwi = {(r[0], r[1], r[2]): sc for r, sc in zip(rows, scores)}
        print(f"[cometkiwi] scored {len(kiwi)} outputs")

    for k in set(comet) | set(kiwi):
        con.execute("DELETE FROM comet_scores WHERE string_id = ? AND engine = ? AND run_id = ?", k)
        con.execute(
            "INSERT INTO comet_scores (string_id, engine, run_id, comet, cometkiwi) VALUES (?, ?, ?, ?, ?)",
            (*k, comet.get(k), kiwi.get(k)),
        )
    con.commit()
    export_csvs(con)
    con.close()


if __name__ == "__main__":
    main()
