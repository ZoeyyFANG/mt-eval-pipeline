"""
Content tiering: risk x value decides how much automation a string may get.

    tier 1  MT + QE spot-check        low risk, routing rules decide review
    tier 2  MT + full review          data loss, irreversible actions, placeholders: never spot-checked
    tier 3  human translation + review legal / privacy claims: no MT pushed
    tier 4  transcreation             high-value copy (upsell, first impression, brand voice): no MT pushed

Rules live in data/tiers.csv (pattern, tier, reason), editable by the PM.
The highest tier among matching rules wins; '@placeholder' matches any string
with a placeholder or markup tag. A per-key override is just an exact-key row.
"""
import csv
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path

from common import extract_tokens

RULES_FILE = Path(__file__).resolve().parent.parent / "data" / "tiers.csv"
TIER_NAMES = {1: "MT + spot-check", 2: "MT + full review", 3: "human translation", 4: "transcreation"}


@lru_cache(maxsize=1)
def rules():
    return list(csv.DictReader(open(RULES_FILE, encoding="utf-8")))


def assign_tier(string_id, source_text):
    best = (1, "default")
    for r in rules():
        p = r["pattern"]
        hit = bool(extract_tokens(source_text)) if p == "@placeholder" else fnmatch(string_id, p)
        if hit and int(r["tier"]) > best[0]:
            best = (int(r["tier"]), r["reason"])
    return best
