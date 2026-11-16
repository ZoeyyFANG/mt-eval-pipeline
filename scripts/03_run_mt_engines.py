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
from config import GATE_RESULTS_FILE, MT_OUTPUTS_FILE, ENGINES, MOCK
from common import ask, token_check, extract_tokens, _stable_int

import requests


def translate_google(text, target="zh-CN"):
    key = os.environ["GOOGLE_TRANSLATE_API_KEY"]
    resp = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        params={"key": key},
        json={"q": text, "target": target, "source": "en", "format": "text"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["data"]["translations"][0]["translatedText"]


def translate_deepl(text, target="ZH-HANS"):
    key = os.environ["DEEPL_API_KEY"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    resp = requests.post(
        f"https://{host}/v2/translate",
        headers={"Authorization": f"DeepL-Auth-Key {key}"},
        json={"text": [text], "source_lang": "EN", "target_lang": target},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["translations"][0]["text"]


CLAUDE_PROMPT = """Translate this software UI string from English into Simplified Chinese (zh-CN).

Rules:
- Output ONLY the translation: no quotes, no explanation.
- Keep every placeholder exactly as written, e.g. {{{{count}}}}, {{{{shortcut}}}}, %s.
- Keep every markup tag exactly as written, e.g. <link>…</link>, <bold>…</bold>, <br></br>; translate the words between tags.

String: {text}"""


def translate_claude(text):
    return ask(CLAUDE_PROMPT.format(text=text), max_tokens=400)


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
            except Exception as e:
                failures += 1
                print(f"[mt] {engine} failed on {item['string_id']}: {e}")
                continue
            outputs.append({
                "string_id": item["string_id"],
                "source_text": item["source_text"],
                "engine": engine,
                "mt_text": mt_text,
                **token_check(item["source_text"], mt_text),
            })
    Path(MT_OUTPUTS_FILE).write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bad = sum(1 for o in outputs if not o["token_ok"])
    print(f"[mt] produced {len(outputs)} translations across {len(ENGINES)} engines "
          f"({failures} failed calls, {bad} with placeholder/markup mismatches).")


if __name__ == "__main__":
    main()
