-- Every pipeline table carries run_id so Power BI can chart everything
-- over time, not just compare engines at a single point. Human tables
-- (human_lqa, qe_labels) are filled by hand, outside CI.

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    commit_sha TEXT,
    timestamp TEXT,
    trigger_type TEXT          -- 'ci' | 'local' | 'mock'
);

CREATE TABLE IF NOT EXISTS source_strings (
    string_id TEXT PRIMARY KEY,
    source_text TEXT,
    text_hash TEXT,
    stratum TEXT,              -- short | medium | placeholder_markup | error | long | colors | dnt
    tags TEXT,                 -- e.g. placeholder;markup;short
    batch INTEGER,
    has_placeholder INTEGER DEFAULT 0,
    tier TEXT,                 -- content tier (risk x value), set later by the PM
    first_seen_run_id TEXT
);

CREATE TABLE IF NOT EXISTS source_gate_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    run_id TEXT,
    gate_label TEXT,           -- auto_approve | needs_context | needs_review
    reason TEXT
);

CREATE TABLE IF NOT EXISTS mt_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,               -- google | deepl | claude
    run_id TEXT,
    mt_text TEXT,
    token_ok INTEGER,          -- deterministic placeholder/markup check
    token_detail TEXT,
    glossary_used INTEGER,     -- 1 = termbase given to this engine (Claude prompt / DeepL glossary)
    term_total INTEGER,        -- termbase terms found in the source
    term_hits INTEGER,         -- of those, translated as the termbase says
    term_detail TEXT           -- missing:<term>; forbidden:<term>
);

CREATE TABLE IF NOT EXISTS auto_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,
    run_id TEXT,
    bleu REAL,
    chrf REAL,
    ter REAL
);

CREATE TABLE IF NOT EXISTS llm_judge_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,
    run_id TEXT,
    error_type TEXT,
    severity INTEGER,          -- 1-6, task-impact scale (see 05_llm_judge.py)
    rationale TEXT
);

-- Offline, filled by scripts/comet_scores.py (heavy model, not run in CI).
CREATE TABLE IF NOT EXISTS comet_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,
    run_id TEXT,
    comet REAL,                -- reference-based (validation only)
    cometkiwi REAL             -- reference-free QE
);

-- Binary ground truth for evaluating the QE (scripts/load_qe_labels.py).
CREATE TABLE IF NOT EXISTS qe_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,
    run_id TEXT,
    has_error INTEGER,         -- 1 = contains an error, 0 = acceptable
    error_note TEXT,
    annotator TEXT,
    timestamp TEXT
);

-- Full MQM on a subset, same 1-6 scale as llm_judge_scores.
CREATE TABLE IF NOT EXISTS human_lqa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    engine TEXT,
    error_type TEXT,
    severity INTEGER,
    evaluator TEXT,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS context_enrichment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    string_id TEXT,
    run_id TEXT,
    generated_context TEXT,
    translation_without_context TEXT,
    translation_with_context TEXT,
    edit_distance_formatting INTEGER,
    edit_distance_meaning INTEGER
);
