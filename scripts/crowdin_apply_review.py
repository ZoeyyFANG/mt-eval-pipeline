"""
Apply reviewer corrections to Crowdin: add the corrected translation and approve it.

    python3 scripts/crowdin_apply_review.py data/review/review_corrections.csv

The CSV needs string_id and corrected_zh (plus reason and reviewer, kept for the
record). Each correction is placeholder-checked before it is sent. Run
crowdin_pull_review.py afterwards to measure the edits.
"""
import csv
import functools
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from common import token_check

API = "https://api.crowdin.com/api/v2"
FILE_NAME = "en.json"
TARGET = "zh-CN"


def check(resp, ok_codes=()):
    if resp.status_code in ok_codes:
        return {}
    if not resp.ok:
        raise SystemExit(f"Crowdin HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.text else {}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/review/review_corrections.csv"
    fixes = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"
    s.request = functools.partial(s.request, timeout=30)

    files = check(s.get(f"{API}/projects/{pid}/files", params={"limit": 500}))["data"]
    fid = next(f["data"]["id"] for f in files if f["data"]["name"] == FILE_NAME)
    strings = check(s.get(f"{API}/projects/{pid}/strings", params={"fileId": fid, "limit": 500}))["data"]
    ids = {st["data"]["identifier"].strip('"'): (st["data"]["id"], st["data"]["text"]) for st in strings}

    done = 0
    for f in fixes:
        sid, zh = f["string_id"], f["corrected_zh"]
        if sid not in ids:
            print(f"[review] {sid}: not in Crowdin, skipped")
            continue
        cid, source = ids[sid]
        if not token_check(source, zh)["token_ok"]:
            print(f"[review] {sid}: placeholder mismatch in the correction, skipped")
            continue
        tr = check(s.post(f"{API}/projects/{pid}/translations",
                          json={"stringId": cid, "languageId": TARGET, "text": zh}), ok_codes=(400, 409))
        tid = tr.get("data", {}).get("id")
        if not tid:  # same text already exists: find it
            ex = check(s.get(f"{API}/projects/{pid}/translations",
                             params={"stringId": cid, "languageId": TARGET, "limit": 50}))["data"]
            tid = next((t["data"]["id"] for t in ex if t["data"]["text"] == zh), None)
        if tid:
            check(s.post(f"{API}/projects/{pid}/approvals", json={"translationId": tid}), ok_codes=(400, 409))
            check(s.post(f"{API}/projects/{pid}/comments",
                         json={"stringId": cid, "targetLanguageId": TARGET, "type": "comment",
                               "text": f"[review] corrected: {f.get('reason', '')} ({f.get('reviewer', '')})"}))
            done += 1
            print(f"[review] {sid}: {zh}")
    print(f"[review] {done}/{len(fixes)} corrections added and approved")


if __name__ == "__main__":
    main()
