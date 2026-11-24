"""
Pull approved zh-CN translations back from Crowdin and measure reviewer edits.

    python3 scripts/crowdin_pull_review.py

For every approved string: compare the final text with the MT candidate the
pipeline pushed (latest route) -> post-edit distance (0 = shipped untouched,
1 = fully rewritten). Results go to the review_edits table and a per-route
summary is printed. The approved strings are written to locales/zh-CN.json,
which the auto-PR step ships back to the repo.

Only APPROVED translations are pulled: an unapproved MT suggestion is not a
reviewer decision.
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from config import DB_PATH, SCHEMA_FILE, ROOT

API = "https://api.crowdin.com/api/v2"
FILE_NAME = "en.json"
TARGET = "zh-CN"
OUT_FILE = ROOT / "locales" / "zh-CN.json"


def flatten(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from flatten(v, key)
        else:
            yield key, v


def edit_distance(a, b):
    """Character Levenshtein distance divided by the longer length (0..1)."""
    if a == b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), len(b), 1)


def main():
    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"
    files = s.get(f"{API}/projects/{pid}/files", params={"limit": 500}).json()["data"]
    fid = next(f["data"]["id"] for f in files if f["data"]["name"] == FILE_NAME)
    r = s.post(f"{API}/projects/{pid}/translations/builds/files/{fid}",
               json={"targetLanguageId": TARGET, "exportApprovedOnly": True,
                     "skipUntranslatedStrings": True})
    if not r.ok:
        raise SystemExit(f"Crowdin HTTP {r.status_code}: {r.text[:300]}")
    approved = dict(flatten(requests.get(r.json()["data"]["url"], timeout=30).json()))

    con = sqlite3.connect(DB_PATH)
    con.executescript(Path(SCHEMA_FILE).read_text(encoding="utf-8"))
    routes = {sid: (route, eng, mt) for sid, route, eng, mt in con.execute(
        """SELECT string_id, route, engine, mt_text FROM routes
           WHERE id IN (SELECT MAX(id) FROM routes GROUP BY string_id)""")}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    by_route = defaultdict(list)
    rows = []
    for sid, final in approved.items():
        route, eng, mt = routes.get(sid, ("unrouted", None, None))
        dist = edit_distance(mt, final) if mt else None
        rows.append((sid, now, route, eng, mt, final, dist))
        if dist is not None:
            by_route[route].append(dist)
    con.executemany("""INSERT INTO review_edits (string_id, pulled_at, route, engine, mt_text, final_text, edit_distance)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""", rows)
    con.commit()

    OUT_FILE.write_text(json.dumps(dict(sorted(approved.items())), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"[crowdin] {len(approved)} approved strings -> {OUT_FILE.relative_to(ROOT)}")
    for route, d in sorted(by_route.items()):
        untouched = sum(x == 0 for x in d)
        print(f"[review] {route:17s} n={len(d):3d}  untouched {untouched}/{len(d)}  "
              f"mean edit distance {sum(d) / len(d):.2f}")


if __name__ == "__main__":
    main()
