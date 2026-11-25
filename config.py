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
EXPORT_DIR = Path(os.environ.get("MT_EVAL_EXPORT_DIR") or ROOT / "data" / "exports")   # CSVs for Excel / Power BI

# --- history replay (scripts/replay_history.py sets MT_EVAL_REPLAY=1) ---
# Same steps, separate sandbox: its own locale file, snapshot, scratch files,
# DB and exports, so replaying Excalidraw's history never touches the main
# run, its routes or what was pushed to Crowdin.
REPLAY = os.environ.get("MT_EVAL_REPLAY") == "1"
if REPLAY:
    _NAME = os.environ.get("MT_EVAL_REPLAY_NAME", "replay")   # replay_mock for dry runs
    _R = ROOT / "data" / _NAME
    LOCALE_FILE = _R / "en.json"
    SNAPSHOT_FILE = _R / "last_processed_en.json"
    PENDING_FILE = _R / "_pending_batch.json"
    GATE_RESULTS_FILE = _R / "_gate_results.json"
    MT_OUTPUTS_FILE = _R / "_mt_outputs.json"
    AUTO_METRICS_FILE = _R / "_auto_metrics.json"
    LLM_JUDGE_FILE = _R / "_llm_judge.json"
    DB_PATH = ROOT / "db" / f"{_NAME}.db"
    EXPORT_DIR = _R / "exports"

# --- model / engines ---
# Override with the ANTHROPIC_MODEL env var if your account uses a different model.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ENGINES = [e.strip() for e in os.environ.get("MT_EVAL_ENGINES", "google,deepl,claude").split(",") if e.strip()]

# Set MT_EVAL_SKIP_LLM=1 when no Claude API access: the source gate falls back to
# rules and the LLM judge is skipped (re-run it later on the stored outputs).
SKIP_LLM = os.environ.get("MT_EVAL_SKIP_LLM") == "1"

# Set MT_EVAL_MOCK=1 to run the whole pipeline with fake API responses
# (no keys, no cost) — used for tests and demos.
MOCK = os.environ.get("MT_EVAL_MOCK") == "1"

# Termbase (data/terms/termbase.csv) is fed to the engines that support it:
# Claude via the prompt, DeepL via a glossary. Google v2 has no glossary support.
# Set MT_EVAL_USE_GLOSSARY=0 to run every engine without it (ablation).
USE_GLOSSARY = os.environ.get("MT_EVAL_USE_GLOSSARY", "1") != "0"

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

# Router thresholds (step 8). Set from the ROC / routing analysis, not guessed:
# held-out batches 2-4: rules + severity <= 2 met the risk target (1.3 errors / 100 shipped).
SPOT_CHECK_MAX_SEVERITY = int(os.environ.get("MT_EVAL_SPOT_MAX", "2"))
REPAIR_MIN_SEVERITY = 4
