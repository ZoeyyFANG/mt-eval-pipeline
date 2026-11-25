"""
Source-quality gate, version 2 — and an evaluation of v1 vs v2.

v1 (02_source_gate.py) asked one LLM call to judge everything and sent a
string to needs_context for ANY of: placeholder, plural, ambiguity. Result:
48% of strings flagged, most of them only because they contain {{...}},
which is already guarded by the deterministic token check after MT.

v2 splits the work the way a loc engineer would:
  rules (free, exact)   empty / whitespace at the edges -> needs_review
                        sentence split across keys (…line1, …line2) -> needs_context
                        placeholder / markup  -> info only (token check after MT)
                        count-dependent text  -> info only for zh-CN (CLDR: Chinese
                        has one plural form), would block for e.g. ru / pl
  LLM (one narrow job)  is the string ambiguous for a translator? If so, name
                        the possible senses and write the question to ask the dev.
Decision: needs_review > needs_context > auto_approve.

    python scripts/source_gate_v2.py --eval     # 180 labelled strings, v1 vs v2 report
    python scripts/source_gate_v2.py --mock --eval

Ground truth here is indirect: the human QE labels say which strings ended up
with translation errors. A useful gate flags FEW strings and catches MANY of
the errors (high lift). It does not prove the flagged strings needed context;
item 6 tests that directly (translate with vs without context).
"""
import argparse, csv, json, os, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ap = argparse.ArgumentParser()
ap.add_argument("--eval", action="store_true")
ap.add_argument("--mock", action="store_true")
ARGS = ap.parse_args()
if ARGS.mock:
    os.environ["MT_EVAL_MOCK"] = "1"
from config import DB_PATH, EXPORT_DIR, ROOT          # noqa: E402
from common import ask_json, extract_tokens           # noqa: E402

LAB = ROOT / "labels"
SPLIT = re.compile(r"^(.*)[._](line|part)?(\d+)$", re.I)
RULE_CAUGHT = {"placeholder", "locale", "terminology"}   # blocked by token / punctuation / termbase checks after MT
COUNTY = re.compile(r"\{\{\s*(count|num|n|number|total)\s*\}\}|\w\(s\)", re.I)

AMBIG_PROMPT = """You screen English UI strings before translation into Chinese (Simplified).
App: Excalidraw, a whiteboard / diagram editor. The key tells you roughly where the string lives.

Key: {key}
String: "{text}"

Only question: could a professional translator, seeing just the key and the string, reasonably
pick a WRONG meaning? (e.g. "Line" = the line tool vs stroke style; "Thin" = stroke width vs
thin font; "Saving" = status "saving..." vs a verb button; "Library" = asset library vs code library)
Do NOT flag a string just because it is short, contains placeholders, or because politeness
or register might vary. Flag only a real fork in meaning that the key does not resolve.

Reply ONLY with JSON:
{{"ambiguous": true|false, "senses": ["<sense 1>", "<sense 2>"], "question": "<one question to ask the developer, or empty>"}}"""


def rule_flags(sid, text, all_ids):
    f = {}
    if not text.strip():
        f["empty"] = True
    if text != text.strip() and text.strip():
        f["edge_whitespace"] = True            # often a sign of string concatenation in code
    m = SPLIT.match(sid)
    if m:
        stem = m.group(1)
        siblings = [k for k in all_ids if k != sid and k.startswith(stem) and SPLIT.match(k)
                    and SPLIT.match(k).group(1) == stem]
        if siblings:
            f["split_sentence"] = True         # one message cut into several keys
    if extract_tokens(text):
        f["placeholder_or_markup"] = True
    if COUNTY.search(text):
        f["count_dependent"] = True
    return f


def mock_ambig(text):
    one = len(text.split()) <= 1
    return json.dumps({"ambiguous": one, "senses": [], "question": "mock" if one else ""})


def ambiguity(sid, text):
    try:
        r = ask_json(AMBIG_PROMPT.format(key=sid, text=text), max_tokens=250, mock_reply=lambda _: mock_ambig(text))
        return bool(r.get("ambiguous")), r.get("senses") or [], r.get("question", "")
    except Exception as e:                     # an unreliable answer never auto-approves
        return None, [], f"gate call failed: {e}"


def decide(flags, amb):
    if flags.get("empty"):
        return "needs_review", "empty string"
    if amb is None:
        return "needs_review", "ambiguity check failed"
    if flags.get("split_sentence"):
        return "needs_context", "sentence split across keys: translate the whole message together"
    if flags.get("edge_whitespace"):
        return "needs_context", "leading/trailing space: likely concatenated in code"
    if amb:
        return "needs_context", "meaning is ambiguous without product context"
    return "auto_approve", "clear; placeholders/plurals handled downstream" if (
        flags.get("placeholder_or_markup") or flags.get("count_dependent")) else "clear"


def labelled():
    """string_id -> (errors, labels) over every engine output a human labelled."""
    out = defaultdict(lambda: [0, 0, 0])   # errors, labels, meaning errors
    for lab, key in (("qe_labels_zoey.csv", "_key_zoey.csv"), ("qe_labels_zoey_b2.csv", "_key_zoey_b2.csv")):
        keys = {r["item_id"]: r["string_id"] for r in csv.DictReader(open(LAB / key, encoding="utf-8-sig"))}
        for r in csv.DictReader(open(LAB / lab, encoding="utf-8-sig")):
            o = out[keys[r["item_id"]]]; o[0] += int(r["has_error"]); o[1] += 1
            tag = (r["error_note"] or "").strip().split(" ")[0].lower()
            if r["has_error"] == "1" and tag not in RULE_CAUGHT:
                o[2] += 1
    return out


def summarize(rows, col):
    flagged = [r for r in rows if r[col] != "auto_approve"]
    e_all = sum(r["errors"] for r in rows); n_all = sum(r["n"] for r in rows)
    e_f = sum(r["errors"] for r in flagged); n_f = sum(r["n"] for r in flagged)
    e_u, n_u = e_all - e_f, n_all - n_f
    rate = lambda e, n: 100 * e / n if n else 0
    lift = (rate(e_f, n_f) / rate(e_all, n_all)) if n_f and e_all else 0
    m_all = sum(r["meaning_errors"] for r in rows); m_f = sum(r["meaning_errors"] for r in flagged)
    return {"flagged_strings": len(flagged), "flag_rate": 100 * len(flagged) / len(rows),
            "err_rate_flagged": rate(e_f, n_f), "err_rate_unflagged": rate(e_u, n_u),
            "errors_caught": e_f, "errors_total": e_all, "recall": rate(e_f, e_all), "lift": lift,
            "meaning_recall": rate(m_f, m_all), "meaning_total": m_all}


def main():
    if not ARGS.eval:
        sys.exit("only --eval for now; v2 replaces 02_source_gate.py after the history replay finishes")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    src = dict(con.execute("SELECT string_id, source_text FROM source_strings"))
    v1 = dict(con.execute("""SELECT string_id, gate_label FROM source_gate_results
                             WHERE id IN (SELECT MAX(id) FROM source_gate_results GROUP BY string_id)"""))
    def flat(d, p=""):
        o = {}
        for k, v in d.items():
            kk = f"{p}.{k}" if p else k
            o.update(flat(v, kk) if isinstance(v, dict) else {kk: v})
        return o
    full = flat(json.loads((ROOT / "data" / "string_pool" / "excalidraw_en_full.json").read_text(encoding="utf-8")))
    all_ids = list(full)
    lab = labelled()
    rows = []
    for i, (sid, (e, n, me)) in enumerate(sorted(lab.items()), 1):
        text = src.get(sid, full.get(sid, ""))
        flags = rule_flags(sid, text, all_ids)
        amb, senses, q = ambiguity(sid, text)
        label, why = decide(flags, amb)
        rows.append({"string_id": sid, "source_en": text, "errors": e, "n": n, "meaning_errors": me, "v1": v1.get(sid, ""),
                     "v2": label, "v2_reason": why, "flags": ";".join(flags), "ambiguous": amb,
                     "senses": " | ".join(senses), "question_for_dev": q})
        print(f"[gate2] {i}/{len(lab)} {sid}: {label}" + (f" ({why})" if label != "auto_approve" else ""), flush=True)

    EXPORT_DIR.mkdir(exist_ok=True)
    with open(EXPORT_DIR / "source_gate_eval.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    s1, s2 = summarize(rows, "v1"), summarize(rows, "v2")
    only_ph = sum(1 for r in rows if r["v1"] == "needs_context" and r["v2"] == "auto_approve"
                  and "placeholder_or_markup" in r["flags"])
    md = ["# Source gate: v1 vs v2", "",
          f"{len(rows)} strings with human QE labels ({s1['errors_total']} error labels over all engine outputs).", "",
          "| | v1 (one LLM call decides all) | v2 (rules + narrow LLM) |", "|---|---|---|"]
    for k, name in (("flagged_strings", "Strings held before MT"), ("flag_rate", "Share held %"),
                    ("err_rate_flagged", "Error rate, held strings %"), ("err_rate_unflagged", "Error rate, passed strings %"),
                    ("recall", "Share of all errors in held strings %"), ("lift", "Lift (held error rate / overall)"),
                    ("meaning_recall", "Share of meaning errors in held strings % (errors the post-MT rules can't catch)")):
        md.append(f"| {name} | {s1[k]:.1f} | {s2[k]:.1f} |" if isinstance(s1[k], float) else f"| {name} | {s1[k]} | {s2[k]} |")
    md += ["", f"- {only_ph} strings v1 held only for a placeholder are passed by v2: the token check after MT already blocks a broken placeholder.",
           "- Count-dependent strings are recorded, not held: zh-CN has one plural form (CLDR), so no ICU plural variants are needed. For ru / pl / ar they would be held.",
           "", "## Questions v2 would send to the developer", ""]
    md += [f"- `{r['string_id']}` \"{r['source_en']}\": {r['question_for_dev']}" for r in rows
           if r["ambiguous"] and r["question_for_dev"]][:25]
    (EXPORT_DIR / "source_gate_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:14]))


if __name__ == "__main__":
    main()
