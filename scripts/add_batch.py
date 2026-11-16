"""
Simulate a new release: merge string batch N into locales/en.json.

    python scripts/add_batch.py 2

Commit + push after running it, and the GitHub Action treats the new
keys as freshly added strings (new run_id, new timestamp). Run batches
2, 3 and 4 on different days to get real time points for the dashboard.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LOCALE_FILE, ROOT

n = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: python scripts/add_batch.py <batch number>")
batch = json.loads((ROOT / "data" / "string_pool" / f"batch_{n}.json").read_text(encoding="utf-8"))
current = json.loads(Path(LOCALE_FILE).read_text(encoding="utf-8"))
added = [k for k in batch if k not in current]
current.update(batch)
Path(LOCALE_FILE).write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[batch] added {len(added)} strings from batch {n}; en.json now has {len(current)}")
