"""
Download the Chinese translations from Crowdin and use them as the
reference translations (gold standard).

    python3 scripts/crowdin_pull_refs.py            # all translated strings
    python3 scripts/crowdin_pull_refs.py --approved # only approved ones

Writes them into data/reference_worksheet.csv (reference_zh column) and
then rebuilds data/references.json with the usual placeholder check.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from config import WORKSHEET_FILE

API = "https://api.crowdin.com/api/v2"
FILE_NAME = "en.json"
TARGET = "zh-CN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approved", action="store_true", help="export approved translations only")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    # Once MT has been pushed to Crowdin (crowdin_push_mt.py), zh-CN holds machine
    # translations: pulling them as references would contaminate the gold standard.
    import sqlite3
    from config import DB_PATH
    con = sqlite3.connect(DB_PATH)
    has_routes = con.execute("SELECT name FROM sqlite_master WHERE name='routes'").fetchone() and \
        con.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
    if has_routes and not a.force:
        sys.exit("[crowdin] MT has been pushed to Crowdin, so zh-CN is no longer a clean reference. "
                 "Use crowdin_pull_review.py for reviewer edits. (--force to override)")

    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"

    files = s.get(f"{API}/projects/{pid}/files", params={"limit": 500}).json()["data"]
    fid = next(f["data"]["id"] for f in files if f["data"]["name"] == FILE_NAME)
    r = s.post(f"{API}/projects/{pid}/translations/builds/files/{fid}",
               json={"targetLanguageId": TARGET, "exportApprovedOnly": a.approved,
                     "skipUntranslatedStrings": True})
    if not r.ok:
        raise SystemExit(f"Crowdin HTTP {r.status_code}: {r.text[:300]}")
    translated = requests.get(r.json()["data"]["url"], timeout=30).json()

    rows = list(csv.DictReader(open(WORKSHEET_FILE, encoding="utf-8-sig")))
    filled = 0
    for row in rows:
        zh = translated.get(row["string_id"])
        if zh:
            row["reference_zh"] = zh
            filled += 1
    with open(WORKSHEET_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"[crowdin] pulled {filled} translations into the worksheet")
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "build_references.py")])


if __name__ == "__main__":
    main()
