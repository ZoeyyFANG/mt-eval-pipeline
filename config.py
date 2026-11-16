"""
Central config for the pipeline. Every script imports paths and
settings from here so they only exist in one place — change the
engine list or the MQM rubric once, not in six files.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- inputs you maintain by hand ---
LOCALE_FILE = ROOT / "locales" / "en.json"            # source-of-truth UI strings
REFERENCES_FILE = ROOT / "data" / "references.json"    # built from the worksheet by build_references.py
WORKSHEET_FILE = ROOT / "data" / "reference_worksheet.csv"  # strata/tags per string + your references
LABELS_DIR = ROOT / "labels"                            # binary QE labels (one CSV per annotator)

# --- state the pipeline maintains itself ---
SNAPSHOT_FILE = ROOT / "data" / "last_processed_en.json"  # what's already been scored

# --- scratch files passed between pipeline steps (safe to delete anytime) ---
PENDING_FILE = ROOT / "data" / "_pending_batch.json"
GATE_RESULTS_FILE = ROOT / "data" / "_gate_results.json"
MT_OUTPUTS_FILE = ROOT / "data" / "_mt_outputs.json"
AUTO_METRICS_FILE = ROOT / "data" / "_auto_metrics.json"
LLM_JUDGE_FILE = ROOT / "data" / "_llm_judge.json"

# --- database ---
DB_PATH = ROOT / "db" / "pipeline.db"
SCHEMA_FILE = ROOT / "db" / "schema.sql"
EXPORT_DIR = ROOT / "data" / "exports"   # CSVs for Excel / Power BI to read

# --- model / engines ---
# Override with the ANTHROPIC_MODEL env var if your account uses a different model.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ENGINES = ["google", "deepl", "claude"]

# Set MT_EVAL_MOCK=1 to run the whole pipeline with fake API responses
# (no keys, no cost) — used for tests and demos.
MOCK = os.environ.get("MT_EVAL_MOCK") == "1"

# --- MQM-lite rubric used by the LLM judge (05_llm_judge.py) ---
MQM_ERROR_TYPES = [
    "accuracy",             # meaning changed or lost
    "terminology",          # wrong or inconsistent term for a known concept
    "fluency",              # grammatical / unnatural phrasing
    "locale_convention",    # punctuation, date/number format, honorifics, etc.
    "placeholder_mismatch", # {{name}}, %s, <link>…</link> dropped, altered or reordered wrongly
    "truncation_risk",      # translation likely too long for a UI element
    "style",                # tone mismatch, not wrong but off-brand
    "none",                 # no issue
]
