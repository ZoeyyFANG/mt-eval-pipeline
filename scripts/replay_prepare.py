"""
Replay prep: cut Excalidraw's real en.json history into quarterly batches.

Each batch = en.json as it stood on master at the end of a quarter.
Replaying them in order through the pipeline gives a real content
timeline (what new strings each quarter brought), instead of one
random sample scored once.

    python scripts/replay_prepare.py                 # clones to ~/.cache/mt-eval/excalidraw
    python scripts/replay_prepare.py --src <clone>   # use an existing clone

Writes data/replay/points/<label>.json (flat key -> text) and
data/replay/points.csv. Needs network once; the replay itself does not.
Limitation: this replays CONTENT drift only. Engines are called as they
are today, so engine drift is tracked going forward (regression set).
"""
import argparse, csv, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "replay"
REPO = "https://github.com/excalidraw/excalidraw.git"
PINNED = "dd2f8fc32b92cbf56f4abee6a0cf3b14681b4b55"   # same commit as data/string_pool/SOURCE.md
EN_PATH = "packages/excalidraw/locales/en.json"
BASELINE = ("2025Q1_baseline", "v0.18.0")             # treated as already localized, not scored
CUTOFFS = [("2025Q2", "2025-06-30"), ("2025Q3", "2025-09-30"), ("2025Q4", "2025-12-31"),
           ("2026Q1", "2026-03-31"), ("2026Q2", "2026-06-30"), ("2026Q3", "2026-09-30"),
           ("2026Q4", None)]                           # None = pinned commit (2026-11-03)


def git(src, *args):
    return subprocess.run(["git", "-C", str(src), *args], capture_output=True, text=True, check=True).stdout


def flat(d, p=""):
    out = {}
    for k, v in d.items():
        kk = f"{p}.{k}" if p else k
        out.update(flat(v, kk) if isinstance(v, dict) else {kk: v})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path.home() / ".cache" / "mt-eval" / "excalidraw"))
    src = Path(ap.parse_args().src)
    if not (src / ".git").exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", REPO, str(src)], check=True)

    (OUT / "points").mkdir(parents=True, exist_ok=True)
    rows, prev, prev_sha = [], None, None
    for label, cutoff in [(BASELINE[0], "tag")] + CUTOFFS:
        if cutoff == "tag":
            sha = git(src, "rev-list", "-1", BASELINE[1]).strip()
        elif cutoff is None:
            sha = PINNED
        else:
            sha = git(src, "rev-list", "-1", f"--before={cutoff} 23:59:59", PINNED).strip()
        date = git(src, "log", "-1", "--format=%cs", sha).strip()
        strings = flat(json.loads(git(src, "show", f"{sha}:{EN_PATH}")))
        (OUT / "points" / f"{label}.json").write_text(
            json.dumps(strings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        new = sum(k not in prev for k in strings) if prev else 0
        changed = sum(k in prev and prev[k] != v for k, v in strings.items()) if prev else 0
        removed = sum(k not in strings for k in prev) if prev else 0
        commits = len(git(src, "log", "--format=%h", f"{prev_sha}..{sha}", "--", EN_PATH).split()) if prev_sha else 0
        rows.append({"label": label, "date": date, "commit": sha[:10], "total": len(strings),
                     "new": new, "changed": changed, "removed": removed, "en_json_commits": commits})
        print(f"[replay-prep] {label} {date} {sha[:10]} total={len(strings)} new={new} changed={changed}")
        prev, prev_sha = strings, sha

    with open(OUT / "points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
