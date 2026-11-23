"""
Termbase as pipeline data (language assets as prompt data).

data/terms/termbase.csv is the single source of truth. This module:
  - finds which terms occur in a source string (longest match first)
  - builds the per-string glossary block for the Claude prompt
  - builds DeepL glossary entries (one-to-one, unambiguous terms only)
  - checks term adherence of any MT output (used for every engine,
    so Google, which gets no glossary, is measured the same way)
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

TERMBASE = Path(__file__).resolve().parent.parent / "data" / "terms" / "termbase.csv"


@lru_cache(maxsize=1)
def load_terms():
    if not TERMBASE.exists():
        return []
    rows = list(csv.DictReader(open(TERMBASE, encoding="utf-8-sig")))
    terms = []
    for r in rows:
        # "Ctrl / Cmd / Alt ..." style rows are notes, not single terms
        if "/" in r["term_en"]:
            continue
        terms.append({
            "en": r["term_en"], "zh": r["zh"], "dnt": r["do_not_translate"] == "yes",
            "note": r["note"], "forbidden": r.get("forbidden_zh", ""),
            # ambiguous terms go to the prompt (with their note) but not to
            # DeepL's hard glossary or the adherence score
            "ambiguous": "ambiguous" in r["note"].lower() or "check context" in r["note"].lower(),
            "status": r["status"],
        })
    return sorted(terms, key=lambda t: -len(t["en"]))


def _pattern(en):
    # word boundaries; allow simple plural / -s forms (arrow -> arrows)
    return re.compile(r"(?<![\w+])" + re.escape(en) + r"(?:s|es)?(?![\w+])", re.IGNORECASE)


def matching_terms(source):
    """Terms found in the source, longest first; a span is claimed once
    (so 'color picker' wins over 'color')."""
    found, taken = [], []
    for t in load_terms():
        hit = False
        for m in _pattern(t["en"]).finditer(source):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            hit = True
        if hit:
            found.append(t)
    return found


def prompt_block(source):
    terms = matching_terms(source)
    if not terms:
        return ""
    lines = []
    for t in terms:
        if t["dnt"]:
            lines.append(f"- {t['en']}: do not translate, keep as {t['zh']}")
        else:
            extra = f" ({t['note']})" if t["ambiguous"] and t["note"] else ""
            bad = f"; never {t['forbidden']}" if t["forbidden"] else ""
            lines.append(f"- {t['en']} → {t['zh']}{bad}{extra}")
    return "Glossary (use these translations):\n" + "\n".join(lines) + "\n\n"


def deepl_entries():
    """TSV for a DeepL EN->ZH glossary: one-to-one, unambiguous terms."""
    rows = []
    for t in load_terms():
        if t["ambiguous"]:
            continue
        rows.append(f"{t['en']}\t{t['zh']}")
    return "\n".join(rows)


def term_adherence(source, mt_text, string_id=""):
    """How many glossary terms in the source got their termbase translation.
    Keyboard key names (keys.*) are left as printed on the key, so they are skipped."""
    if string_id.startswith("keys."):
        return {"term_total": 0, "term_hits": 0, "term_detail": ""}
    checked = [t for t in matching_terms(source) if not t["ambiguous"]]
    missing = [t["en"] for t in checked if t["zh"] not in mt_text]
    forbidden = [t["en"] for t in checked if t["forbidden"] and t["forbidden"] in mt_text]
    return {
        "term_total": len(checked),
        "term_hits": len(checked) - len(missing),
        "term_detail": "; ".join([f"missing:{m}" for m in missing] + [f"forbidden:{f}" for f in forbidden]),
    }
