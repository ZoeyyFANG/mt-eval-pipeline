"""
Runs the full pipeline locally in order — the exact sequence the
GitHub Action runs in CI. Use this to test everything on your machine
before wiring up the workflow, and to do your first manual run.
"""
import subprocess
import sys
from pathlib import Path

STEPS = [
    "01_diff_detect.py",
    "02_source_gate.py",
    "03_run_mt_engines.py",
    "04_auto_metrics.py",
    "05_llm_judge.py",
    "06_write_db.py",
    "08_route.py",
]

SCRIPTS_DIR = Path(__file__).resolve().parent


def preflight():
    """Fail fast instead of producing a run full of failed API calls."""
    import os
    sys.path.insert(0, str(SCRIPTS_DIR.parent))
    sys.path.insert(0, str(SCRIPTS_DIR))
    import common  # noqa: F401  (loads .env)
    from config import MOCK, SKIP_LLM, ENGINES
    if MOCK:
        return
    need = {"google": "GOOGLE_TRANSLATE_API_KEY", "deepl": "DEEPL_API_KEY"}
    missing = [need[e] for e in ENGINES if e in need and not os.environ.get(need[e])]
    if ("claude" in ENGINES or not SKIP_LLM) and not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"[pipeline] missing keys: {', '.join(missing)}. Add them to .env (local) or "
              f"repo Secrets (CI), or use MT_EVAL_SKIP_LLM / MT_EVAL_ENGINES. Nothing was run.")
        sys.exit(1)


def main():
    preflight()
    for step in STEPS:
        print(f"\n=== running {step} ===")
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / step)])
        if result.returncode != 0:
            print(f"[pipeline] {step} failed, stopping.")
            sys.exit(1)
    print("\n[pipeline] done. Check data/exports/ for the CSVs.")


if __name__ == "__main__":
    main()
