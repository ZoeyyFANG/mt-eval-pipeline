"""
Step 2: Automated source-quality gate.

Mirrors "an LLM checks source strings before they reach localization
and auto-approves the safe ones, with plural forms, empty values and
unreliable responses deliberately kept out of auto-approval." Runs
BEFORE any translation happens, so an obviously-unsafe string gets
flagged instead of silently producing bad MT output that nobody
catches until QA.
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PENDING_FILE, GATE_RESULTS_FILE, SKIP_LLM
from common import ask_json, extract_tokens

GATE_PROMPT = """You are screening a UI source string before it enters a machine-translation pipeline.

Source string: "{text}"

Decide:
1. Does it contain placeholders or markup that must survive translation (e.g. {{{{count}}}}, %s, <link>…</link>)?
2. Is it a plural-form pattern (its meaning depends on a count)?
3. Is it empty, whitespace-only, or clearly not natural-language content (e.g. a raw code/config value)?
4. Is it ambiguous without product context (e.g. a single word like "Close", "Line", "Open" that could be a verb or a noun)?

Respond ONLY with compact JSON:
{{"placeholder": bool, "plural": bool, "empty_or_code": bool, "ambiguous": bool, "gate_label": "auto_approve" | "needs_context" | "needs_review", "reason": "<one short sentence>"}}

gate_label rules: "needs_review" if empty_or_code is true; else "needs_context" if placeholder, plural, or ambiguous is true; else "auto_approve".
"""

LABELS = {"auto_approve", "needs_context", "needs_review"}


def mock_gate(text):
    has_tok = bool(extract_tokens(text))
    empty = not text.strip()
    ambiguous = len(text.split()) <= 2
    label = ("needs_review" if empty else
             "needs_context" if has_tok or ambiguous else "auto_approve")
    return {"placeholder": has_tok, "plural": "count" in text, "empty_or_code": empty,
            "ambiguous": ambiguous, "gate_label": label, "reason": "mock"}


def screen_one(text):
    if SKIP_LLM:  # rule-based fallback: same labels, no model
        gate = mock_gate(text)
        gate["reason"] = "rule-based gate (LLM unavailable)"
        return gate
    gate = ask_json(GATE_PROMPT.format(text=text), max_tokens=200,
                    mock_reply=lambda _: json.dumps(mock_gate(text)))
    # never trust an unexpected label: unknown -> needs_review
    if gate.get("gate_label") not in LABELS:
        gate["gate_label"] = "needs_review"
        gate["reason"] = f"unparseable gate label; sent to review ({gate.get('reason', '')})"
    return gate


def main():
    pending = json.loads(Path(PENDING_FILE).read_text(encoding="utf-8"))
    results = []
    for item in pending:
        try:
            gate = screen_one(item["source_text"])
        except Exception as e:  # an unreliable response never auto-approves
            gate = {"gate_label": "needs_review", "reason": f"gate call failed: {e}"}
        results.append({**item, **gate})
        print(f"[gate] {item['string_id']}: {gate['gate_label']} ({gate.get('reason', '')})")
    Path(GATE_RESULTS_FILE).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
