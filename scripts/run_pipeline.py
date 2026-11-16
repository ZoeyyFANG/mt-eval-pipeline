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
]

SCRIPTS_DIR = Path(__file__).resolve().parent


def main():
    for step in STEPS:
        print(f"\n=== running {step} ===")
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / step)])
        if result.returncode != 0:
            print(f"[pipeline] {step} failed, stopping.")
            sys.exit(1)
    print("\n[pipeline] done. Check data/exports/ for the CSVs.")


if __name__ == "__main__":
    main()
