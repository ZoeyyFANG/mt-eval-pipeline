"""
Tag every routed string in Crowdin so the work organises itself:
  route-<route>   e.g. route-full_review, route-spot_check, route-transcreation
  tier-<n>        content tier 1-4
  <batch label>   optional, e.g. upstream-eaa7fa3 (--batch), for "what came in this sync"
Reviewers then filter the editor by label ("show me route-full_review") instead
of reading a spreadsheet. Labels only ever get added, never removed.

    python scripts/crowdin_labels.py [--batch upstream-<sha7>] [--only-new]
--only-new: label only strings first seen in the latest run (CI after a sync).
"""
import argparse, functools, os, sqlite3, sys
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from config import DB_PATH
from crowdin_push_mt import API, check, crowdin_string_ids


def label_ids(s, pid, titles):
    have, offset = {}, 0
    while True:
        page = check(s.get(f"{API}/projects/{pid}/labels", params={"limit": 500, "offset": offset}))["data"]
        have.update({l["data"]["title"]: l["data"]["id"] for l in page})
        if len(page) < 500:
            break
        offset += 500
    for t in titles:
        if t not in have:
            have[t] = check(s.post(f"{API}/projects/{pid}/labels", json={"title": t}))["data"]["id"]
            print(f"[labels] created label {t}")
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch")
    ap.add_argument("--only-new", action="store_true")
    a = ap.parse_args()
    con = sqlite3.connect(DB_PATH)
    q = """SELECT r.string_id, r.route, r.tier FROM routes r
           WHERE r.id IN (SELECT MAX(id) FROM routes GROUP BY string_id)"""
    if a.only_new:
        q += " AND r.string_id IN (SELECT string_id FROM source_strings WHERE first_seen_run_id = (SELECT MAX(run_id) FROM runs))"
    rows = con.execute(q).fetchall()
    want = defaultdict(set)
    for sid, route, tier in rows:
        want[f"route-{route}"].add(sid)
        if tier:
            want[f"tier-{tier}"].add(sid)
        if a.batch:
            want[a.batch].add(sid)
    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"
    s.request = functools.partial(s.request, timeout=30)
    ids = crowdin_string_ids(s, pid)
    labels = label_ids(s, pid, want)
    for title, sids in sorted(want.items()):
        cids = [ids[x] for x in sids if x in ids]
        for i in range(0, len(cids), 100):
            check(s.post(f"{API}/projects/{pid}/labels/{labels[title]}/strings", json={"stringIds": cids[i:i + 100]}))
        print(f"[labels] {title}: {len(cids)} strings")


if __name__ == "__main__":
    main()
