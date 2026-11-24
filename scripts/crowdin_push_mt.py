"""
Push the routed MT candidates to Crowdin as pre-translations (zh-CN).

    python3 scripts/crowdin_push_mt.py                 # push + route comments
    python3 scripts/crowdin_push_mt.py --auto-approve  # also approve spot-check strings not sampled

Run crowdin_push.py first so every source key exists in Crowdin.
For each string, the latest route from 08_route.py decides what happens:
  human_only        nothing pushed: a linguist translates from scratch
  dnt_check         the source text is pushed (keyboard keys stay as printed)
  spot_check        MT pushed; a 10% random sample (min 10) is marked for review,
                    the rest can be auto-approved (--auto-approve) = shipped without review
  full_review / mandatory_review / repair
                    MT pushed and left unapproved for a linguist
Every pushed string gets a comment with route, engine, severity and rule flags,
so reviewers see why it is in their queue. A log goes to data/exports/crowdin_push_log.csv.
"""
import argparse
import functools
import csv
import os
import random
import sqlite3
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (loads .env)
from config import DB_PATH, EXPORT_DIR

API = "https://api.crowdin.com/api/v2"
FILE_NAME = "en.json"
TARGET = "zh-CN"
SAMPLE_RATE, SAMPLE_MIN = 0.10, 10


def check(resp, ok_codes=()):
    if resp.status_code in ok_codes:
        return {}
    if not resp.ok:
        raise SystemExit(f"Crowdin HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.text else {}


def crowdin_string_ids(s, pid):
    files = check(s.get(f"{API}/projects/{pid}/files", params={"limit": 500}))["data"]
    fid = next(f["data"]["id"] for f in files if f["data"]["name"] == FILE_NAME)
    ids, offset = {}, 0
    while True:
        page = check(s.get(f"{API}/projects/{pid}/strings",
                           params={"fileId": fid, "limit": 500, "offset": offset}))["data"]
        for st in page:
            ids[st["data"]["identifier"].strip('"')] = st["data"]["id"]
        if len(page) < 500:
            return ids
        offset += 500


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto-approve", action="store_true",
                    help="approve spot-check strings that were not sampled for review")
    ap.add_argument("--seed", type=int, default=20261123)
    a = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    routes = con.execute("""SELECT string_id, route, engine, mt_text, severity, rule_flags, reason
                            FROM routes WHERE id IN (SELECT MAX(id) FROM routes GROUP BY string_id)""").fetchall()
    if not routes:
        sys.exit("no routes yet: run scripts/08_route.py first")
    # strings the repair agent fixed: push its candidate instead (still reviewed in full)
    try:
        repaired = {sid: cand for sid, cand in con.execute(
            """SELECT string_id, candidate FROM agent_outcomes WHERE outcome = 'repaired'
               AND id IN (SELECT MAX(id) FROM agent_outcomes GROUP BY string_id)""")}
    except sqlite3.OperationalError:
        repaired = {}
    routes = [(sid, route, eng, repaired.get(sid, mt), sev,
               (flags + "; " if flags else "") + "agent-repaired" if sid in repaired else flags, why)
              for sid, route, eng, mt, sev, flags, why in routes]

    spot = sorted(r[0] for r in routes if r[1] == "spot_check")
    rng = random.Random(a.seed)
    sample = set(rng.sample(spot, min(len(spot), max(SAMPLE_MIN, round(SAMPLE_RATE * len(spot))))))

    pid = os.environ["CROWDIN_PROJECT_ID"].strip()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CROWDIN_TOKEN'].strip()}"
    s.request = functools.partial(s.request, timeout=30)  # never hang on one call
    ids = crowdin_string_ids(s, pid)
    print(f"[crowdin] {len(ids)} strings found in Crowdin; pushing {len(routes)} routed strings...", flush=True)

    log, missing = [], 0
    for i, (sid, route, eng, mt, sev, flags, why) in enumerate(routes, 1):
        if i % 20 == 0:
            print(f"[crowdin] {i}/{len(routes)}", flush=True)
        cid = ids.get(sid)
        if cid is None:
            missing += 1
            continue
        if route in ("human_only", "human_translation", "transcreation") or not mt:
            note = {"human_translation": "[pipeline] tier 3: translate from scratch (no MT), second linguist reviews",
                    "transcreation": "[pipeline] tier 4: transcreate from the brief in data/assets/brand_voice.md (no MT)"
                    }.get(route)
            if note:
                check(s.post(f"{API}/projects/{pid}/comments",
                             json={"stringId": cid, "targetLanguageId": TARGET, "text": note, "type": "comment"}))
            log.append((sid, route, "", "", "not pushed"))
            continue
        tr = check(s.post(f"{API}/projects/{pid}/translations",
                          json={"stringId": cid, "languageId": TARGET, "text": mt}), ok_codes=(400, 409))
        tr_id = tr.get("data", {}).get("id")
        label = route + (" (SAMPLED FOR REVIEW)" if sid in sample else "")
        if not tr_id:
            # already pushed in an earlier (interrupted) run: don't add a second comment
            if a.auto_approve and (route == "dnt_check" or (route == "spot_check" and sid not in sample)):
                ex = check(s.get(f"{API}/projects/{pid}/translations",
                                 params={"stringId": cid, "languageId": TARGET, "limit": 50}))["data"]
                match = next((t["data"]["id"] for t in ex if t["data"]["text"] == mt), None)
                if match:
                    check(s.post(f"{API}/projects/{pid}/approvals", json={"translationId": match}),
                          ok_codes=(400, 409))
            log.append((sid, label, eng or "", mt, "already pushed earlier"))
            continue
        note = f"[pipeline] route: {label} | engine: {eng or '-'} | severity: {sev if sev is not None else '-'}"
        if flags:
            note += f" | flags: {flags}"
        check(s.post(f"{API}/projects/{pid}/comments",
                     json={"stringId": cid, "targetLanguageId": TARGET, "text": note, "type": "comment"}))
        status = "pushed" if tr_id else "pushed (translation already existed)"
        if a.auto_approve and tr_id and (route == "dnt_check" or (route == "spot_check" and sid not in sample)):
            check(s.post(f"{API}/projects/{pid}/approvals", json={"translationId": tr_id}))
            status += ", auto-approved"
        log.append((sid, label, eng or "", mt, status))

    EXPORT_DIR.mkdir(exist_ok=True)
    with open(EXPORT_DIR / "crowdin_push_log.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["string_id", "route", "engine", "mt_text", "status"])
        w.writerows(log)
    approved = sum("auto-approved" in r[4] for r in log)
    print(f"[crowdin] {sum(r[4].startswith('pushed') for r in log)} pre-translations pushed, "
          f"{approved} auto-approved, {len(sample)} spot-check strings sampled for review, "
          f"{missing} keys not found in Crowdin (run crowdin_push.py first).")


if __name__ == "__main__":
    main()
