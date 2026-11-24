"""
CI gate for a translated locale file: run on every l10n pull request.

    python3 scripts/check_locale.py                       # locales/zh-CN.json vs locales/en.json
    python3 scripts/check_locale.py --summary out.md      # also write a Markdown summary (PR body)

Blocks the PR (exit 1) when:
  - a key in zh-CN.json does not exist in en.json (stale or typo key)
  - a placeholder or markup tag differs from the source (breaks the UI at runtime)
Reports, but does not block:
  - coverage: keys still missing (they fall back to English at runtime)
  - half-width punctuation in Chinese text
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ROOT
from common import token_check, locale_check


def flat(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from flat(v, key)
        else:
            yield key, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "locales" / "en.json"))
    ap.add_argument("--target", default=str(ROOT / "locales" / "zh-CN.json"))
    ap.add_argument("--summary", help="write a Markdown summary here")
    a = ap.parse_args()

    en = dict(flat(json.loads(Path(a.source).read_text(encoding="utf-8"))))
    zh = dict(flat(json.loads(Path(a.target).read_text(encoding="utf-8"))))

    unknown = sorted(k for k in zh if k not in en)
    missing = sorted(k for k in en if k not in zh)
    token_fail, punct = [], []
    for k, v in zh.items():
        if k not in en:
            continue
        t = token_check(en[k], v)
        if not t["token_ok"]:
            token_fail.append((k, t["token_detail"]))
        loc = locale_check(v)
        if not loc["locale_ok"]:
            punct.append((k, loc["locale_detail"]))

    coverage = 100 * (len(en) - len(missing)) / len(en) if en else 0
    blocked = bool(unknown or token_fail)
    lines = [
        f"## zh-CN locale check: {'❌ blocked' if blocked else '✅ passed'}",
        "",
        f"- Coverage: **{len(en) - len(missing)}/{len(en)} keys ({coverage:.0f}%)**; missing keys fall back to English",
        f"- Placeholder / markup mismatches: **{len(token_fail)}** (blocking)",
        f"- Keys not in en.json: **{len(unknown)}** (blocking)",
        f"- Half-width punctuation in Chinese: {len(punct)} (warning)",
    ]
    for title, items in (("Placeholder / markup mismatches", token_fail),
                         ("Keys not in en.json", [(k, "") for k in unknown]),
                         ("Half-width punctuation", punct),
                         ("Missing keys (English fallback)", [(k, "") for k in missing[:30]])):
        if items:
            lines += ["", f"### {title}", ""] + [f"- `{k}` {d}".rstrip() for k, d in items]
    report = "\n".join(lines)
    print(report)
    if a.summary:
        Path(a.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(a.summary).write_text(report + "\n", encoding="utf-8")
    sys.exit(1 if blocked else 0)


if __name__ == "__main__":
    main()
