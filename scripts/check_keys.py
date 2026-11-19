"""
Check that the three API keys in .env work, with one tiny request each.

    python3 scripts/check_keys.py

Prints OK or the error for each engine. Never prints the keys.
"""
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from config import ANTHROPIC_MODEL

TEXT = "Save"


def check(name, fn):
    try:
        print(f"[OK]   {name}: Save -> {fn()}")
    except KeyError as e:
        print(f"[MISS] {name}: {e} is not set in .env")
    except Exception as e:
        import re
        detail = ""
        resp = getattr(e, "response", None)
        if resp is not None and getattr(resp, "text", None):
            try:
                err = resp.json().get("error", {})
                reasons = [d.get("reason") for d in err.get("details", []) if d.get("reason")]
                detail = f" | {err.get('status', '')}: {err.get('message', '')} {reasons}"
            except Exception:
                detail = " | " + resp.text[:300]
        msg = re.sub(r"(key=|sk-ant-|AIza)[A-Za-z0-9_\-:]+", r"\1***", str(e) + detail)
        print(f"[FAIL] {name}: {msg[:600]}")


def google():
    import importlib
    mt = importlib.import_module("03_run_mt_engines")
    return mt.translate_google(TEXT)


def deepl():
    import importlib
    mt = importlib.import_module("03_run_mt_engines")
    return mt.translate_deepl(TEXT)


def claude():
    os.environ["ANTHROPIC_API_KEY"]  # raise KeyError early if missing
    return common.ask(f"Translate this UI button label into Simplified Chinese. Output only the translation: {TEXT}",
                      max_tokens=20) + f"   (model: {ANTHROPIC_MODEL})"


if __name__ == "__main__":
    check("Google", google)
    check("DeepL", deepl)
    check("Claude", claude)
