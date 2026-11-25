"""
Translator context, generated from real evidence, and measured three ways.

  1. generate   For the strings that need context, Claude writes a 1-2 sentence
                translator note from the context packet (code usage + the commit /
                PR that introduced the string, scripts/context_packets.py).
                -> data/context/context_review.csv  (edited_context pre-filled)
  2. (human)    A reviewer corrects edited_context in place, as a loc PM or
                developer would before the note goes into the TMS.
  3. score      How much did the reviewer have to change? Edit distance split into
                formatting edits (punctuation, spacing, case) and meaning edits
                (words). -> data/exports/context_edit_report.md
  4. translate  Re-translate the same strings with the edited note (Claude in the
                prompt, DeepL via its `context` parameter) -> blind label sheet
                data/context/context_ab_todo.csv; engine + condition in a key file.
  5. ab         Error rate without vs with context, after labelling.
                -> data/exports/context_ab_report.md

Targets: strings whose human-labelled outputs had a meaning error (accuracy /
fluency, the errors the post-MT rules can't catch), plus strings the v2 source
gate called ambiguous (data/exports/source_gate_eval.csv) when that exists.

    python scripts/07_context_enrichment.py generate|score|translate|ab [--mock]

Replaces an earlier stub that used a made-up example ticket.
"""
import argparse, csv, difflib, importlib.util, json, os, random, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["generate", "score", "translate", "ab"])
ap.add_argument("--mock", action="store_true")
ap.add_argument("--max", type=int, default=25)
ARGS = ap.parse_args()
if ARGS.mock:
    os.environ["MT_EVAL_MOCK"] = "1"
from config import ROOT, DB_PATH, EXPORT_DIR, MOCK      # noqa: E402
from common import ask                                  # noqa: E402

CTX = ROOT / "data" / "context"
LAB = ROOT / "labels"
REVIEW = CTX / "context_review.csv"
AB_TODO, AB_KEY, AB_DONE = CTX / "context_ab_todo.csv", CTX / "_key_context_ab.csv", CTX / "context_ab.csv"
RULE_CAUGHT = {"placeholder", "locale", "terminology"}

GEN_PROMPT = """You write translator notes for software UI strings (Excalidraw, a whiteboard / diagram app).
Use ONLY the evidence below. If the evidence does not settle something, do not guess it.

Key: {key}
English string: "{text}"
Where the code uses it:
{usage}
Commit that last changed this string: {commit}

Write ONE note for a translator, at most 25 words: what the string is on screen (button, status,
tooltip, menu label, toast...), its part of speech, and the one wrong sense to avoid if there is one.
State only what the evidence shows: no "presumably", "appears", "likely". No translation advice,
no preamble. Output only the note."""


def targets():
    meaning = defaultdict(int)
    for lab, key in (("qe_labels_zoey.csv", "_key_zoey.csv"), ("qe_labels_zoey_b2.csv", "_key_zoey_b2.csv")):
        keys = {r["item_id"]: r["string_id"] for r in csv.DictReader(open(LAB / key, encoding="utf-8-sig"))}
        for r in csv.DictReader(open(LAB / lab, encoding="utf-8-sig")):
            tag = (r["error_note"] or "").strip().split(" ")[0].lower()
            if r["has_error"] == "1" and tag not in RULE_CAUGHT:
                meaning[keys[r["item_id"]]] += 1
    why = {sid: "meaning error in labelled MT" for sid in meaning}
    g = EXPORT_DIR / "source_gate_eval.csv"
    if g.exists():
        for r in csv.DictReader(open(g, encoding="utf-8-sig")):
            if r["ambiguous"] == "True":
                why[r["string_id"]] = (why[r["string_id"]] + "; " if r["string_id"] in why else "") + "gate v2: ambiguous"
    ids = sorted(why, key=lambda s: (-meaning.get(s, 0), s))[:ARGS.max]
    return ids, why


def fmt_usage(p):
    if not p["usage"]:
        return "(not found in code)"
    return "\n".join(f"{u['file']}:{u['line']}\n{u['snippet']}" for u in p["usage"])


def generate():
    packets = json.loads((CTX / "packets.json").read_text(encoding="utf-8"))
    ids, why = targets()
    rows = []
    for i, sid in enumerate(ids, 1):
        p = packets.get(sid)
        if not p:
            print(f"[ctx] {sid}: no packet, skipped"); continue
        note = ask(GEN_PROMPT.format(key=sid, text=p["source_en"], usage=fmt_usage(p),
                                     commit=f"{p['commit_subject']} ({p['pr_url'] or 'no PR link'})"),
                   max_tokens=200, mock_reply=lambda _: f"Mock note for {sid}.").strip()
        ev = "; ".join(f"{u['file']}:{u['line']}" for u in p["usage"]) or "no code usage"
        rows.append({"string_id": sid, "source_en": p["source_en"], "why_selected": why[sid],
                     "evidence": f"{ev}; {p['pr_url'] or ''}", "generated_context": note,
                     "edited_context": note, "reviewer_note": ""})
        print(f"[ctx] {i}/{len(ids)} {sid}: {note}", flush=True)
    with open(REVIEW, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"[ctx] {len(rows)} notes -> {REVIEW.relative_to(ROOT)}. Edit `edited_context` in place.")


def norm_words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def is_subseq(short, long):
    """Reviewer only deleted words (cut length), added or changed nothing."""
    it = iter(long)
    return all(w in it for w in short)


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def score():
    rows = list(csv.DictReader(open(REVIEW, encoding="utf-8-sig")))
    out, kinds = [], defaultdict(int)
    for r in rows:
        g, e = r["generated_context"], r["edited_context"]
        total = lev(g, e) / max(len(g), len(e), 1)                       # character level, everything
        gw, ew = norm_words(g), norm_words(e)
        meaning = lev(gw, ew) / max(len(gw), len(ew), 1)                 # word level, punctuation/case/space ignored
        kind = ("unchanged" if g == e else "formatting_only" if gw == ew
                else "trimmed_only" if is_subseq(ew, gw) else "meaning")
        kinds[kind] += 1
        out.append((r["string_id"], kind, total, meaning, r.get("reviewer_note", "")))
    n = len(out)
    md = ["# Generated translator context: how much did the reviewer change?", "",
          f"{n} notes generated from code usage + commit/PR. Reviewed by: "
          f"{', '.join(sorted({r.get('reviewer') or 'a person' for r in rows}))}.", "",
          "| Outcome | Notes | Share |", "|---|---|---|"]
    md += [f"| {k} | {kinds[k]} | {100*kinds[k]/n:.0f}% |" for k in ("unchanged", "formatting_only", "trimmed_only", "meaning")]
    md += ["", f"- Mean character edit distance (all edits): {sum(o[2] for o in out)/n:.2f}",
           f"- Mean word edit distance (meaning edits only): {sum(o[3] for o in out)/n:.2f}",
           "- Formatting-only and trimmed-only edits can be automated away (style rules, a length cap in the prompt);",
           "  meaning edits (words added or changed) mean the evidence or the model was wrong: those are the ones that matter.",
           "", "## Meaning edits", ""]
    md += [f"- `{o[0]}` word distance {o[3]:.2f}" + (f": {o[4]}" if o[4] else "") for o in out if o[1] == "meaning"]
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / "context_edit_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def load_engine_module():
    spec = importlib.util.spec_from_file_location("mt03", ROOT / "scripts" / "03_run_mt_engines.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def translate():
    m = load_engine_module()
    rows = list(csv.DictReader(open(REVIEW, encoding="utf-8-sig")))
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    items = []
    for r in rows:
        sid, src, ctx = r["string_id"], r["source_en"], r["edited_context"].strip()
        for eng in ("claude", "deepl"):
            old = con.execute("""SELECT mt_text FROM mt_outputs WHERE string_id = ? AND engine = ?
                                 ORDER BY id DESC LIMIT 1""", (sid, eng)).fetchone()
            if not old:
                continue
            if MOCK:
                new = f"[{eng}+ctx] {src}"
            elif eng == "claude":
                glossary = m.prompt_block(src) if m.USE_GLOSSARY else ""
                new = ask(m.CLAUDE_PROMPT.format(text=src, glossary=glossary +
                          f"Translator context: {ctx}\n\n"), max_tokens=400)
            else:
                host, headers = m._deepl_host_headers()
                body = {"text": [src], "source_lang": "EN", "target_lang": "ZH-HANS", "context": ctx}
                if m.USE_GLOSSARY:
                    body["glossary_id"] = m.deepl_glossary_id()
                resp = m.requests.post(f"https://{host}/v2/translate", headers=headers, json=body, timeout=20)
                resp.raise_for_status(); new = resp.json()["translations"][0]["text"]
            items.append({"string_id": sid, "engine": eng, "condition": "no_context", "mt_zh": old[0], "source_en": src})
            items.append({"string_id": sid, "engine": eng, "condition": "with_context", "mt_zh": new, "source_en": src})
            print(f"[ctx-mt] {sid} / {eng}: {old[0]}  ->  {new}", flush=True)
    random.Random(20261124).shuffle(items)
    with open(AB_TODO, "w", newline="", encoding="utf-8-sig") as f, open(AB_KEY, "w", newline="", encoding="utf-8-sig") as k:
        w = csv.DictWriter(f, fieldnames=["item_id", "context_key", "source_en", "mt_zh", "has_error", "error_note"])
        kw = csv.DictWriter(k, fieldnames=["item_id", "string_id", "engine", "condition"])
        w.writeheader(); kw.writeheader()
        for i, it in enumerate(items, 1):
            iid = f"c{i:03d}"
            # same columns as the QE sheets, same GUIDELINES; condition and engine stay in the key file
            w.writerow({"item_id": iid, "context_key": it["string_id"], "source_en": it["source_en"],
                        "mt_zh": it["mt_zh"], "has_error": "", "error_note": ""})
            kw.writerow({"item_id": iid, "string_id": it["string_id"], "engine": it["engine"], "condition": it["condition"]})
    print(f"[ctx-mt] {len(items)} rows -> {AB_TODO.relative_to(ROOT)} (label blind, save as context_ab.csv)")


def ab():
    keys = {r["item_id"]: r for r in csv.DictReader(open(AB_KEY, encoding="utf-8-sig"))}
    res = defaultdict(lambda: [0, 0]); pair = defaultdict(dict)
    for r in csv.DictReader(open(AB_DONE, encoding="utf-8-sig")):
        if r["has_error"].strip() not in ("0", "1"):
            continue
        k = keys[r["item_id"]]; e = int(r["has_error"])
        res[(k["engine"], k["condition"])][0] += e; res[(k["engine"], k["condition"])][1] += 1
        pair[(k["string_id"], k["engine"])][k["condition"]] = e
    md = ["# Does generated context fix errors? (blind labels)", "",
          "| Engine | Without context: errors / n | With context: errors / n | Fixed | Broken |", "|---|---|---|---|---|"]
    for eng in ("claude", "deepl"):
        a, b = res[(eng, "no_context")], res[(eng, "with_context")]
        ps = [v for (s, e), v in pair.items() if e == eng and len(v) == 2]
        fixed = sum(v["no_context"] == 1 and v["with_context"] == 0 for v in ps)
        broke = sum(v["no_context"] == 0 and v["with_context"] == 1 for v in ps)
        md.append(f"| {eng} | {a[0]} / {a[1]} | {b[0]} / {b[1]} | {fixed} | {broke} |")
    md += ["", "Targets were chosen because they had errors, so the no-context error rate is high by design; "
           "read Fixed vs Broken, not the absolute rates. The no-context rows are re-labelled here, blind, "
           "next to the new ones, so both conditions are judged in the same sitting."]
    (EXPORT_DIR / "context_ab_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    {"generate": generate, "score": score, "translate": translate, "ab": ab}[ARGS.cmd]()
