"""
Turn the reference worksheet you translate in Excel into data/references.json.

    python scripts/build_references.py

Only rows with a filled `reference_zh` are written, so you can translate
in chunks and re-run this any time. It also runs a quick self-check on
your own references: placeholders ({{x}}) and markup tags (<link>…</link>)
must survive exactly — the same rule the LLM judge applies to the engines.
"""
import csv, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import REFERENCES_FILE, ROOT

WORKSHEET = ROOT / "data" / "reference_worksheet.csv"
TOKEN = re.compile(r"\{\{\s*\w+\s*\}\}|</?\w+>")


def main():
    rows = list(csv.DictReader(open(WORKSHEET, encoding="utf-8-sig")))
    refs, problems = {}, []
    for r in rows:
        ref = (r.get("reference_zh") or "").strip()
        if not ref:
            continue
        refs[r["string_id"]] = ref
        if sorted(TOKEN.findall(r["source_en"])) != sorted(TOKEN.findall(ref)):
            problems.append(r["string_id"])
    Path(REFERENCES_FILE).write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
    done = sum(1 for r in rows if (r.get("reference_zh") or "").strip())
    print(f"[refs] {done}/{len(rows)} references written to {REFERENCES_FILE.name}")
    for b in sorted({r['batch'] for r in rows}):
        n = [r for r in rows if r["batch"] == b]
        print(f"       batch {b}: {sum(1 for r in n if (r.get('reference_zh') or '').strip())}/{len(n)}")
    if problems:
        print(f"[refs] placeholder/markup mismatch in your own reference for: {', '.join(problems)}")


if __name__ == "__main__":
    main()
