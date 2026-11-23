"""Convert data/terms/termbase.csv to TBX (TBX-Basic style) for TMS import."""
import csv, sys
from xml.sax.saxutils import escape as e
src = sys.argv[1] if len(sys.argv) > 1 else "data/terms/termbase.csv"
out = sys.argv[2] if len(sys.argv) > 2 else "data/terms/termbase.tbx"
rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<tbx type="TBX-Basic" style="dca" xml:lang="en" xmlns="urn:iso:std:iso:30042:ed-2">',
         '<tbxHeader><fileDesc><sourceDesc><p>Excalidraw EN-ZH termbase (mt-eval-pipeline)</p></sourceDesc></fileDesc></tbxHeader>',
         '<text><body>']
for r in rows:
    parts.append(f'<conceptEntry id="{e(r["id"])}">')
    parts.append(f'<descrip type="subjectField">{e(r["subject"])}</descrip>')
    parts.append(f'<descrip type="definition">{e(r["definition_en"])}</descrip>')
    parts.append(f'<langSec xml:lang="en"><termSec><term>{e(r["term_en"])}</term>'
                 f'<termNote type="partOfSpeech">{e(r["pos"])}</termNote>'
                 f'<descrip type="context">{e(r["context_en"])}</descrip></termSec></langSec>')
    parts.append(f'<langSec xml:lang="zh-CN"><termSec><term>{e(r["zh"])}</term>'
                 f'<termNote type="administrativeStatus">{"preferredTerm-admn-sts" if r["status"]=="approved" else "admittedTerm-admn-sts"}</termNote>'
                 f'<note>{e(r["note"])}</note></termSec>')
    if r.get("forbidden_zh"):
        parts.append(f'<termSec><term>{e(r["forbidden_zh"])}</term>'
                     f'<termNote type="administrativeStatus">deprecatedTerm-admn-sts</termNote></termSec>')
    parts.append('</langSec></conceptEntry>')
parts.append('</body></text></tbx>')
open(out, "w", encoding="utf-8").write("\n".join(parts))
print(f"wrote {len(rows)} entries -> {out}")
