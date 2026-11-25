"""
Step 3: Run every engine on every gated string.

Same source string, same run_id, three engines — the "one sample
runs through every engine" pattern, instead of picking one engine
and trusting it. Strings flagged needs_review by the gate are
skipped here on purpose (a code/empty value shouldn't be auto-
translated at all).

Every output also gets the deterministic placeholder/markup check
(token_ok), which the router uses as a hard rule.
"""
import json
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import GATE_RESULTS_FILE, MT_OUTPUTS_FILE, ENGINES, MOCK, USE_GLOSSARY
from common import ask, token_check, extract_tokens, _stable_int
from terms import prompt_block, deepl_entries, term_adherence
import hashlib

import requests


def translate_google(text, target="zh-CN"):
    key = os.environ["GOOGLE_TRANSLATE_API_KEY"].strip()
    resp = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        params={"key": key},
        json={"q": text, "target": target, "source": "en", "format": "text"},
        timeout=20,
    )
    if not resp.ok:  # raise without the URL, so the key never lands in logs
        try:
            err = resp.json().get("error", {})
            reasons = [d.get("reason") for d in err.get("details", []) if d.get("reason")]
            detail = f"{err.get('status', '')}: {err.get('message', '')} {reasons}"
        except ValueError:
            detail = resp.text[:300]
        raise RuntimeError(f"Google HTTP {resp.status_code} | {detail}")
    return resp.json()["data"]["translations"][0]["translatedText"]


def _deepl_host_headers():
    key = os.environ["DEEPL_API_KEY"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    return host, {"Authorization": f"DeepL-Auth-Key {key}"}


_DEEPL_GLOSSARY = {}


class GlossaryError(RuntimeError):
    """Setup problem, not a per-string failure: stop the step instead of
    producing a batch with one engine silently missing."""


def deepl_glossary_id():
    """Reuse a DeepL glossary whose name carries the termbase hash. If the termbase
    changed, delete this pipeline's stale glossaries (DeepL Free holds only one)
    and upload the current one."""
    if "id" in _DEEPL_GLOSSARY:
        return _DEEPL_GLOSSARY["id"]
    entries = deepl_entries()
    name = "mt-eval-termbase-" + hashlib.sha1(entries.encode()).hexdigest()[:8]
    host, headers = _deepl_host_headers()
    existing = requests.get(f"https://{host}/v2/glossaries", headers=headers, timeout=20)
    existing.raise_for_status()
    for g in existing.json().get("glossaries", []):
        if g["name"] == name and g.get("ready"):
            _DEEPL_GLOSSARY["id"] = g["glossary_id"]
            return g["glossary_id"]
    for g in existing.json().get("glossaries", []):
        if g["name"].startswith("mt-eval-termbase-"):   # only ours, never anything else
            requests.delete(f"https://{host}/v2/glossaries/{g['glossary_id']}",
                            headers=headers, timeout=20).raise_for_status()
            print(f"[mt] deleted stale DeepL glossary {g['name']} (termbase changed)")
    resp = requests.post(f"https://{host}/v2/glossaries", headers=headers, timeout=20,
                         json={"name": name, "source_lang": "en", "target_lang": "zh",
                               "entries": entries, "entries_format": "tsv"})
    if not resp.ok:
        raise GlossaryError(f"DeepL glossary upload failed: {resp.status_code} {resp.text[:200]}")
    gid = resp.json()["glossary_id"]
    print(f"[mt] created DeepL glossary {name} ({resp.json().get('entry_count')} entries)")
    _DEEPL_GLOSSARY["id"] = gid
    return gid


def translate_deepl(text, target="ZH-HANS"):
    host, headers = _deepl_host_headers()
    body = {"text": [text], "source_lang": "EN", "target_lang": target}
    if USE_GLOSSARY:
        body["glossary_id"] = deepl_glossary_id()
    resp = requests.post(
        f"https://{host}/v2/translate",
        headers=headers,
        json=body,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["translations"][0]["text"]


CLAUDE_PROMPT = """Translate this software UI string from English into Simplified Chinese (zh-CN).

Rules:
- Output ONLY the translation: no quotes, no explanation.
- Keep every placeholder exactly as written, e.g. {{{{count}}}}, {{{{shortcut}}}}, %s.
- Keep every markup tag exactly as written, e.g. <link>…</link>, <bold>…</bold>, <br></br>; translate the words between tags.

{glossary}String: {text}"""


def translate_claude(text):
    glossary = prompt_block(text) if USE_GLOSSARY else ""
    return ask(CLAUDE_PROMPT.format(text=text, glossary=glossary), max_tokens=400)


def mock_translate(engine, text):
    """Fake output for tests: keeps tokens, but one engine sometimes drops one."""
    out = f"[{engine}] {text}"
    toks = extract_tokens(text)
    if toks and engine == "google" and _stable_int(text, 3) == 0:
        out = out.replace(toks[0], "", 1)
    return out


ENGINE_FUNCS = {
    "google": translate_google,
    "deepl": translate_deepl,
    "claude": translate_claude,
}


def main():
    gated = json.loads(Path(GATE_RESULTS_FILE).read_text(encoding="utf-8"))
    outputs, failures = [], 0
    for item in gated:
        if item["gate_label"] == "needs_review":
            print(f"[mt] skipping {item['string_id']} — flagged needs_review, not auto-translating")
            continue
        for engine in ENGINES:
            try:
                mt_text = (mock_translate(engine, item["source_text"]) if MOCK
                           else ENGINE_FUNCS[engine](item["source_text"]))
            except GlossaryError as e:
                sys.exit(f"[mt] stopping: {e}. Nothing from this step was saved.")
            except Exception as e:
                failures += 1
                print(f"[mt] {engine} failed on {item['string_id']}: {e}")
                continue
            outputs.append({
                "string_id": item["string_id"],
                "source_text": item["source_text"],
                "engine": engine,
                "mt_text": mt_text,
                "glossary_used": int(USE_GLOSSARY and engine in ("claude", "deepl")),
                **token_check(item["source_text"], mt_text),
                **term_adherence(item["source_text"], mt_text, item["string_id"]),
            })
    Path(MT_OUTPUTS_FILE).write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bad = sum(1 for o in outputs if not o["token_ok"])
    print(f"[mt] produced {len(outputs)} translations across {len(ENGINES)} engines "
          f"({failures} failed calls, {bad} with placeholder/markup mismatches).")
    for engine in ENGINES:
        rows = [o for o in outputs if o["engine"] == engine]
        total = sum(o["term_total"] for o in rows)
        hits = sum(o["term_hits"] for o in rows)
        if total:
            print(f"[mt] {engine}: term adherence {hits}/{total} ({hits / total:.0%})")


if __name__ == "__main__":
    main()
