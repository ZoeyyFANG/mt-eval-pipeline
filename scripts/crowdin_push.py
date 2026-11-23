"""
Upload the source strings to Crowdin so reference translations are done
in a real TMS editor (with its QA checks and glossary), not in Excel.

    python3 scripts/crowdin_push.py            # uploads locales/en.json (create or update)

Needs in .env:  CROWDIN_TOKEN=...   CROWDIN_PROJECT_ID=123456

Each string also gets translator context: its stratum and tags from the
worksheet, so the linguist sees e.g. "short | ambiguous single word".
"""
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from common import load_strata
from config import LOCALE_FILE

API = "https://api.crowdin.com/api/v2"
FILE_NAME = "en.json"


def session():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"
    return s


def check(resp):
    if not resp.ok:
        raise SystemExit(f"Crowdin HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.text else {}


def main():
    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = session()

    # 1. upload the file to Crowdin storage
    data = Path(LOCALE_FILE).read_bytes()
    storage = check(s.post(f"{API}/storages", data=data,
                           headers={"Crowdin-API-FileName": FILE_NAME,
                                    "Content-Type": "application/json"}))["data"]["id"]

    # 2. create the project file, or update it if it already exists
    files = check(s.get(f"{API}/projects/{pid}/files", params={"limit": 500}))["data"]
    existing = next((f["data"] for f in files if f["data"]["name"] == FILE_NAME), None)
    if existing:
        check(s.put(f"{API}/projects/{pid}/files/{existing['id']}", json={"storageId": storage}))
        file_id = existing["id"]
        print(f"[crowdin] updated {FILE_NAME} (file {file_id})")
    else:
        file_id = check(s.post(f"{API}/projects/{pid}/files",
                               json={"storageId": storage, "name": FILE_NAME}))["data"]["id"]
        print(f"[crowdin] created {FILE_NAME} (file {file_id})")

    # 3. add translator context to every string
    strata = load_strata()
    strings = check(s.get(f"{API}/projects/{pid}/strings",
                          params={"fileId": file_id, "limit": 500}))["data"]
    def key_of(identifier):
        # Crowdin may show a flat JSON key as-is, as a path ("a->b"), or with a file prefix
        ident = identifier.strip('"')  # Crowdin wraps flat JSON keys in quotes
        for cand in (ident, ident.replace("->", "."), ident.split("/")[-1]):
            if cand in strata:
                return cand
        return None

    n = 0
    for st in strings:
        st = st["data"]
        key = key_of(st["identifier"])
        meta = strata.get(key) if key else None
        if not meta:
            continue
        context = f"{key} | type: {meta['stratum']} | tags: {meta['tags'] or '-'}"
        check(s.patch(f"{API}/projects/{pid}/strings/{st['id']}",
                      json=[{"op": "replace", "path": "/context", "value": context}]))
        n += 1
    print(f"[crowdin] {len(strings)} strings in project; context added to {n}.")
    if n == 0 and strings:
        print("[crowdin] sample identifiers:", [x["data"]["identifier"] for x in strings[:3]])


if __name__ == "__main__":
    main()
