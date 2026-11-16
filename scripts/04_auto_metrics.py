"""
Step 4: Reference-based metrics (BLEU / chrF++ / TER) against your own
reference translations.

These need a reference, so they validate the QE offline; they never
route live strings (see the design doc, "Quality assurance and
sampling"). Chinese has no spaces, so BLEU uses sacrebleu's 'zh'
tokenizer and TER its Asian-language support — without them the
scores are meaningless.
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MT_OUTPUTS_FILE, REFERENCES_FILE, AUTO_METRICS_FILE

from sacrebleu.metrics import BLEU, CHRF, TER

bleu = BLEU(tokenize="zh", effective_order=True)
chrf = CHRF(word_order=2)          # word_order=2 makes it chrF++
ter = TER(asian_support=True)


def main():
    outputs = json.loads(Path(MT_OUTPUTS_FILE).read_text(encoding="utf-8"))
    ref_path = Path(REFERENCES_FILE)
    references = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else {}

    scored, skipped = [], 0
    for item in outputs:
        ref = references.get(item["string_id"])
        if not ref:
            skipped += 1
            continue
        hyp = item["mt_text"]
        scored.append({
            "string_id": item["string_id"], "engine": item["engine"], "reference": ref,
            "bleu": bleu.sentence_score(hyp, [ref]).score,
            "chrf": chrf.sentence_score(hyp, [ref]).score,
            "ter": ter.sentence_score(hyp, [ref]).score,
        })

    Path(AUTO_METRICS_FILE).write_text(
        json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[metrics] scored {len(scored)} outputs, skipped {skipped} "
          f"(no reference yet — fill the worksheet, then run build_references.py).")


if __name__ == "__main__":
    main()
