"""
Shared helpers: .env loading, the Claude client (with retries and a
mock mode), robust JSON parsing, and the rule-based placeholder/markup
check. The token check is deliberately NOT left to an LLM: a broken
{{count}} or <link> must be caught every time, deterministically.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ROOT, ANTHROPIC_MODEL, MOCK  # noqa: E402

try:  # optional: lets local runs read keys from .env
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# {{count}}, {name}, %s / %1$s, <link>, </link>, <br/>
TOKEN_RE = re.compile(r"\{\{\s*[\w.]+\s*\}\}|\{[\w.]+\}|%\d*\$?[sd]|</?\w+\s*/?>")


def extract_tokens(text):
    return [re.sub(r"\s+", "", t) for t in TOKEN_RE.findall(text or "")]


def token_check(source, target):
    """Same placeholders and tags, same counts, in any order."""
    src, tgt = Counter(extract_tokens(source)), Counter(extract_tokens(target))
    missing = sorted((src - tgt).elements())
    extra = sorted((tgt - src).elements())
    return {
        "token_ok": not missing and not extra,
        "token_detail": "" if not (missing or extra)
        else f"missing={missing} extra={extra}",
    }


_client = None


def _claude():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(max_retries=4)  # reads ANTHROPIC_API_KEY
    return _client


def _stable_int(text, mod):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % mod


def ask(prompt, max_tokens=300, mock_reply=None):
    """One Claude call. In mock mode returns mock_reply(prompt) instead."""
    if MOCK:
        return mock_reply(prompt) if mock_reply else "{}"
    kwargs = {}
    # Sonnet 5.5 thinks by default (and rejects "disabled"); short classification /
    # translation calls don't need it, and thinking would eat the max_tokens budget.
    if ANTHROPIC_MODEL.startswith("claude-sonnet-5-5"):
        kwargs["thinking"] = {"type": "between_tools"}
    msg = _claude().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    # the reply may hold thinking blocks before the text: keep only text blocks
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if not text:
        raise RuntimeError(f"no text in reply (stop_reason={msg.stop_reason})")
    return text


def ask_json(prompt, max_tokens=300, mock_reply=None, attempts=2):
    """Ask for JSON; tolerate code fences or stray prose; retry once."""
    raw = ""
    for _ in range(attempts):
        raw = ask(prompt, max_tokens, mock_reply)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError(f"model did not return JSON: {raw[:200]!r}")


def load_strata():
    """string_id -> {'stratum', 'tags', 'batch'} from the reference worksheet."""
    import csv
    from config import WORKSHEET_FILE
    if not Path(WORKSHEET_FILE).exists():
        return {}
    with open(WORKSHEET_FILE, encoding="utf-8-sig") as f:
        return {r["string_id"]: r for r in csv.DictReader(f)}


MASTER_VIEW = """
    SELECT s.string_id, s.stratum, s.tags, s.batch, s.source_text,
           m.engine, m.run_id, r.timestamp, m.mt_text, m.token_ok, m.token_detail,
           m.glossary_used, m.term_total, m.term_hits, m.term_detail,
           g.gate_label,
           am.bleu, am.chrf, am.ter,
           cs.comet, cs.cometkiwi,
           lj.error_type AS llm_error_type, lj.severity AS llm_severity, lj.rationale AS llm_rationale,
           ql.has_error AS human_has_error,
           h.error_type AS human_error_type, h.severity AS human_severity
    FROM mt_outputs m
    JOIN source_strings s ON s.string_id = m.string_id
    JOIN runs r ON r.run_id = m.run_id
    LEFT JOIN source_gate_results g ON g.string_id = m.string_id AND g.run_id = m.run_id
    LEFT JOIN auto_metrics am ON am.string_id = m.string_id AND am.engine = m.engine AND am.run_id = m.run_id
    LEFT JOIN comet_scores cs ON cs.string_id = m.string_id AND cs.engine = m.engine AND cs.run_id = m.run_id
    LEFT JOIN llm_judge_scores lj ON lj.string_id = m.string_id AND lj.engine = m.engine AND lj.run_id = m.run_id
    LEFT JOIN (SELECT string_id, engine, run_id, MAX(has_error) AS has_error
               FROM qe_labels WHERE annotator = 'zoey' GROUP BY string_id, engine, run_id) ql
           ON ql.string_id = m.string_id AND ql.engine = m.engine AND ql.run_id = m.run_id
    LEFT JOIN human_lqa h ON h.string_id = m.string_id AND h.engine = m.engine
"""


def export_csvs(con):
    """Write every table plus master_view to data/exports/ as CSV (UTF-8 with BOM for Excel)."""
    import csv
    from config import EXPORT_DIR
    Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    tables = ["runs", "source_strings", "source_gate_results", "mt_outputs", "auto_metrics",
              "llm_judge_scores", "comet_scores", "qe_labels", "human_lqa", "context_enrichment"]
    views = {t: f"SELECT * FROM {t}" for t in tables}
    views["master_view"] = MASTER_VIEW  # the one Power BI / Excel should point at
    for name, query in views.items():
        cur = con.execute(query)
        cols = [d[0] for d in cur.description]
        with open(Path(EXPORT_DIR) / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(cur.fetchall())




# --- locale punctuation check -------------------------------------------
# Half-width , ? ! : ; ( ) next to Chinese characters. The LLM judge missed
# most of these in batch 1, so they are checked by rule, like placeholders.
_CJK = r"[一-鿿]"
_HALF_WIDTH_PUNCT = re.compile(rf"{_CJK}[,?!:;()]|[,?!;()]{_CJK}")


_FULL_WIDTH = {",": "，", "?": "？", "!": "！", ":": "：", ";": "；", "(": "（", ")": "）"}
_PROTECTED = re.compile(r"\{\{[^}]*\}\}|<[^>]+>|https?://[^\s<>\"]+")


def fix_zh_punct(mt_text):
    """Auto-fix: half-width , ? ! : ; ( ) next to Chinese -> full-width.
    Deterministic and safe: never touches placeholders, tags or URLs, and never
    touches punctuation between Latin/digits (1,000 / 12:30 / Ctrl+C). Spaces
    around a converted mark are dropped (full-width marks carry their own space).
    Returns (fixed_text, number_of_marks_changed)."""
    text = mt_text or ""
    shielded = [False] * len(text)
    for m in _PROTECTED.finditer(text):
        for i in range(m.start(), m.end()):
            shielded[i] = True
    is_cjk = lambda c: bool(re.match(_CJK, c))
    out, n, i = [], 0, 0
    while i < len(text):
        c = text[i]
        if c in _FULL_WIDTH and not shielded[i]:
            j = len(out) - 1
            while j >= 0 and out[j] == " ":
                j -= 1
            prev = out[j] if j >= 0 else ""
            k = i + 1
            while k < len(text) and text[k] == " ":
                k += 1
            nxt = text[k] if k < len(text) else ""
            if is_cjk(prev) or is_cjk(nxt):
                del out[j + 1:]                      # spaces before the mark
                out.append(_FULL_WIDTH[c]); n += 1
                i = k                                # spaces after the mark
                continue
        out.append(c); i += 1
    return "".join(out), n


def locale_check(mt_text):
    """Return {'locale_ok': bool, 'locale_detail': str} for zh-CN punctuation."""
    clean = re.sub(r"\{\{[^}]*\}\}|<[^>]+>", "", mt_text or "")
    hits = sorted({m.group(0) for m in _HALF_WIDTH_PUNCT.finditer(clean)})
    return {"locale_ok": not hits, "locale_detail": " ".join(hits)}
