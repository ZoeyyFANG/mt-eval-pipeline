"""
Continuous localization trigger: has Excalidraw (upstream) added or changed
English strings since we last looked?

    python scripts/upstream_sync.py            # compare, merge changes into locales/en.json
    python scripts/upstream_sync.py --dry-run  # only report

State: data/upstream_last.json = the upstream commit and strings we last synced.
New / changed keys are merged into locales/en.json; from there the normal
pipeline (diff -> gate -> MT -> QE -> route) only processes those keys.
Writes data/upstream_changes.md (used as the pull request body) and, in
GitHub Actions, the step outputs `changed` and `count`.
Removed upstream keys are reported, never deleted automatically.
"""
import argparse, json, os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
REPO = "excalidraw/excalidraw"
EN = "packages/excalidraw/locales/en.json"
STATE = ROOT / "data" / "upstream_last.json"
LOCALE = ROOT / "locales" / "en.json"
REPORT = ROOT / "data" / "upstream_changes.md"


def flat(d, p=""):
    o = {}
    for k, v in d.items():
        kk = f"{p}.{k}" if p else k
        o.update(flat(v, kk) if isinstance(v, dict) else {kk: v})
    return o


def latest_upstream():
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    c = requests.get(f"https://api.github.com/repos/{REPO}/commits", params={"path": EN, "per_page": 1},
                     headers=h, timeout=30)
    c.raise_for_status()
    sha = c.json()[0]["sha"]
    msg = c.json()[0]["commit"]["message"].splitlines()[0]
    raw = requests.get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{EN}", timeout=30)
    raw.raise_for_status()
    return sha, msg, flat(raw.json())


def set_output(**kv):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    sha, msg, up = latest_upstream()
    if sha == state["commit"]:
        print(f"[upstream] no change since {sha[:10]}"); set_output(changed="false", count=0); return
    old = state["strings"]
    new = {k: v for k, v in up.items() if k not in old}
    changed = {k: v for k, v in up.items() if k in old and old[k] != v}
    removed = [k for k in old if k not in up]
    print(f"[upstream] {state['commit'][:10]} -> {sha[:10]}: {len(new)} new, {len(changed)} changed, {len(removed)} removed")
    lines = [f"Upstream Excalidraw `en.json` moved from `{state['commit'][:10]}` to "
             f"[`{sha[:10]}`](https://github.com/{REPO}/commit/{sha}) (latest: {msg}).", "",
             f"- **{len(new)} new** and **{len(changed)} changed** strings were merged into `locales/en.json` "
             "and run through the pipeline (gate → MT → QE → route) and pushed to Crowdin with route/tier labels.",
             f"- {len(removed)} keys were removed upstream; they are listed here, not deleted automatically."]
    for title, keys in (("New", new), ("Changed", changed)):
        if keys:
            lines += ["", f"<details><summary>{title} ({len(keys)})</summary>", ""]
            lines += [f"- `{k}`: {v[:90]}" for k, v in keys.items()] + ["", "</details>"]
    if removed:
        lines += ["", "Removed upstream: " + ", ".join(f"`{k}`" for k in removed)]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if a.dry_run:
        print("\n".join(lines)); return
    if new or changed:
        loc = json.loads(LOCALE.read_text(encoding="utf-8"))
        loc.update(new); loc.update(changed)
        LOCALE.write_text(json.dumps(loc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATE.write_text(json.dumps({"commit": sha, "strings": up}, ensure_ascii=False, indent=2), encoding="utf-8")
    set_output(changed="true" if (new or changed) else "false", count=len(new) + len(changed))


if __name__ == "__main__":
    main()
