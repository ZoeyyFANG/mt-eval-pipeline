"""
Build a context packet for every Excalidraw source string, from real sources:
  - where the key is used in the code (file, line, a few lines around it)
  - the commit that last changed the string in en.json (git blame), its subject
    and the pull request number in it -> link to the PR on GitHub
This is what a translator would otherwise have to dig out by hand. Packets are
evidence for scripts/context_generate.py, which writes the translator-facing
note; the packet itself is never shown as "context" without that step.

    python scripts/context_packets.py                  # clones to ~/.cache/mt-eval/excalidraw
    python scripts/context_packets.py --src <clone>

Writes data/context/packets.json. Same pinned commit as data/string_pool/SOURCE.md.
"""
import argparse, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINNED = "dd2f8fc32b92cbf56f4abee6a0cf3b14681b4b55"
EN = "packages/excalidraw/locales/en.json"
REPO = "https://github.com/excalidraw/excalidraw"
CODE_DIRS = ["packages", "excalidraw-app"]


def git(src, *a):
    return subprocess.run(["git", "-C", str(src), *a], capture_output=True, text=True, check=True).stdout


def blame_by_key(src):
    """flat key -> (commit, subject) using line-level blame of en.json."""
    out = git(src, "blame", "--line-porcelain", PINNED, "--", EN).splitlines()
    commits, line_commit, i = {}, [], 0
    cur = None
    for ln in out:
        if re.match(r"^[0-9a-f]{40} ", ln):
            cur = ln.split()[0]
        elif ln.startswith("summary "):
            commits.setdefault(cur, ln[8:])
        elif ln.startswith("\t"):
            line_commit.append((cur, ln[1:]))
    keys, stack = {}, []
    for sha, text in line_commit:
        m = re.match(r'\s*"((?:[^"\\]|\\.)+)"\s*:\s*(\{|")', text)
        if m and m.group(2) == "{":
            stack.append(m.group(1))
        elif m:
            keys[".".join(stack + [m.group(1)])] = (sha, commits.get(sha, ""))
        elif re.match(r"\s*\}", text) and stack:
            stack.pop()
    return keys


def load_code(src):
    files = {}
    for d in CODE_DIRS:
        for p in (src / d).rglob("*"):
            if p.suffix in (".ts", ".tsx") and "locales" not in p.parts and "node_modules" not in p.parts \
                    and not p.name.endswith((".test.tsx", ".test.ts")):
                try:
                    files[str(p.relative_to(src))] = p.read_text(encoding="utf-8").splitlines()
                except UnicodeDecodeError:
                    pass
    return files


def usages(key, files, limit=2):
    pats = [f'"{key}"', f"'{key}'", f"`{key}`"]
    hits = []
    for path, lines in files.items():
        for n, line in enumerate(lines):
            if any(p in line for p in pats):
                hits.append({"file": path, "line": n + 1,
                             "snippet": "\n".join(l.rstrip() for l in lines[max(0, n - 3): n + 4])})
                if len(hits) >= limit:
                    return hits, "exact"
    if hits:
        return hits, "exact"
    prefix = key.rsplit(".", 1)[0]            # dynamic keys like t(`colors.${name}`)
    for path, lines in files.items():
        for n, line in enumerate(lines):
            if f"{prefix}." in line and "${" in line:
                return [{"file": path, "line": n + 1,
                         "snippet": "\n".join(l.rstrip() for l in lines[max(0, n - 3): n + 4])}], "dynamic"
    return [], "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path.home() / ".cache" / "mt-eval" / "excalidraw"))
    src = Path(ap.parse_args().src)
    if not (src / ".git").exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", REPO + ".git", str(src)], check=True)
    git(src, "sparse-checkout", "set", *CODE_DIRS)
    git(src, "checkout", "-q", PINNED)

    blame = blame_by_key(src)
    files = load_code(src)
    en = json.loads(git(src, "show", f"{PINNED}:{EN}"))
    packets, stats = {}, {"exact": 0, "dynamic": 0, "none": 0, "with_pr": 0}

    def walk(d, p=""):
        for k, v in d.items():
            kk = f"{p}.{k}" if p else k
            yield from walk(v, kk) if isinstance(v, dict) else [(kk, v)]
    for key, text in walk(en):
        hits, how = usages(key, files)
        sha, subject = blame.get(key, (None, ""))
        pr = re.search(r"\(#(\d+)\)|#(\d+)", subject or "")
        prn = (pr.group(1) or pr.group(2)) if pr else None
        packets[key] = {"source_en": text, "usage": hits, "usage_match": how,
                        "commit": sha[:10] if sha else None, "commit_subject": subject,
                        "pr": int(prn) if prn else None, "pr_url": f"{REPO}/pull/{prn}" if prn else None}
        stats[how] += 1; stats["with_pr"] += bool(prn)
    out = ROOT / "data" / "context"; out.mkdir(parents=True, exist_ok=True)
    (out / "packets.json").write_text(json.dumps(packets, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[packets] {len(packets)} keys: code usage exact {stats['exact']}, dynamic {stats['dynamic']}, "
          f"not found {stats['none']}; linked to a PR {stats['with_pr']}")


if __name__ == "__main__":
    main()
