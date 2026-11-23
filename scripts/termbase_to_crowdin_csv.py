"""Turn data/terms/termbase.csv into a CSV whose headers Crowdin's glossary
import detects automatically (Term [en], Term [zh-CN], Concept Definition ...)."""
import csv
SRC, OUT = "data/terms/termbase.csv", "data/terms/termbase_crowdin.csv"
POS = {"noun": "noun", "verb": "verb", "proper noun": "proper noun", "verb / noun": "noun"}
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Term [en]", "Description [en]", "Part of Speech [en]",
                "Term [zh-CN]", "Note [zh-CN]",
                "Concept Definition", "Concept Subject", "Concept Note"])
    for r in rows:
        note = r["note"]
        if r["do_not_translate"] == "yes":
            note = ("Do not translate. " + note).strip()
        if r["forbidden_zh"]:
            note += f" Forbidden: {r['forbidden_zh']}"
        w.writerow([r["term_en"], f'e.g. "{r["context_en"]}" ({r["context_key"]})',
                    POS.get(r["pos"], "other"), r["zh"], note,
                    r["definition_en"], r["subject"], f'{r["id"]} | {r["status"]}'])
print(f"{len(rows)} terms -> {OUT}")
