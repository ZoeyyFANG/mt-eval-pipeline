"""
Context enrichment experiment — mirrors "LLM-generated context for
translators, assembled from linked product and engineering tickets,
plus metrics for the generation itself: edit distance between the
generated context and the edited one, split into formatting edits
and meaning edits."

Not part of the CI pipeline — run this by hand on a small, chosen
subset of ambiguous strings (the ones the gate flagged needs_context
are good candidates). Fill in CONTEXT_SOURCE with a real snippet from
the GitHub issue/PR that string came from, then run.

It translates the string once cold (no context) and once with the
generated context, then records both plus a rough edit-distance
breakdown between them.
"""
import difflib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, ANTHROPIC_MODEL

from anthropic import Anthropic

client = Anthropic()

# Fill this in with real string_id -> a snippet of the GitHub issue/PR
# description that string actually came from.
CONTEXT_SOURCE = {
    "tooltip.close_panel": (
        "PR #482: adds a collapsible settings panel; this string labels "
        "the icon that collapses it back."
    ),
}


def load_source_text(string_id):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT source_text FROM source_strings WHERE string_id = ?", (string_id,)
    ).fetchone()
    con.close()
    if not row:
        raise ValueError(f"{string_id} not in source_strings yet — run the main pipeline on it first.")
    return row[0]


def generate_context(string_id, ticket_snippet):
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"A UI string with id '{string_id}' comes from this product context:\n"
                f"\"{ticket_snippet}\"\n\n"
                "Write one short sentence of translator-facing context: what does "
                "this string label or do, and is it a verb, noun, or adjective in this UI?"
            ),
        }],
    )
    return msg.content[0].text.strip()


def translate(text, context=None):
    prompt = f'Translate this UI string into Simplified Chinese: "{text}"'
    if context:
        prompt += f"\n\nTranslator context: {context}"
    prompt += "\n\nOutput ONLY the translation."
    msg = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def edit_distance_breakdown(a, b):
    """Heuristic split, not a linguistic tool: buckets each differing
    opcode as 'formatting' if it's only punctuation/whitespace, else
    'meaning'. Good enough to show the *direction* of the effect,
    which is the point of this experiment."""
    sm = difflib.SequenceMatcher(None, a, b)
    formatting_ops, meaning_ops = 0, 0
    punct = " 、，。！？：；\"'"
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changed_a, changed_b = a[i1:i2], b[j1:j2]
        if changed_a.strip(punct) == "" and changed_b.strip(punct) == "":
            formatting_ops += 1
        else:
            meaning_ops += 1
    return formatting_ops, meaning_ops


def main():
    con = sqlite3.connect(DB_PATH)
    ts = datetime.now(timezone.utc).isoformat()
    for string_id, ticket_snippet in CONTEXT_SOURCE.items():
        source_text = load_source_text(string_id)
        context = generate_context(string_id, ticket_snippet)
        cold = translate(source_text)
        warm = translate(source_text, context=context)
        fmt_ops, meaning_ops = edit_distance_breakdown(cold, warm)
        con.execute(
            """INSERT INTO context_enrichment
               (string_id, run_id, generated_context, translation_without_context,
                translation_with_context, edit_distance_formatting, edit_distance_meaning)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (string_id, f"manual_{ts}", context, cold, warm, fmt_ops, meaning_ops),
        )
        print(
            f"[context] {string_id}\n"
            f"  context: {context}\n  cold: {cold}\n  warm: {warm}\n"
            f"  edits (formatting/meaning): {fmt_ops}/{meaning_ops}\n"
        )
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
