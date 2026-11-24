"""
Step 9: bounded remediation agent.

    python3 scripts/09_repair_agent.py            # all strings routed to repair / mandatory_review
    python3 scripts/09_repair_agent.py labels.thin hints.arrowTool

The agent (Claude with tools) works one flagged string at a time. It chooses
its own next step, but only inside hard limits enforced in this code, not in
the prompt:
  - at most MAX_ATTEMPTS candidates submitted per string, then automatic escalation
  - at most MAX_TOOL_CALLS tool calls per string
  - it cannot approve anything: a candidate is accepted only if the deterministic
    checks pass (placeholders, termbase, punctuation) AND a fresh judge verdict
    is <= SPOT_CHECK_MAX_SEVERITY. Even then the string goes to full human review.
  - it cannot change the source, the termbase, the references or the thresholds
  - every tool call is written to agent_steps; every result to agent_outcomes

Tools
  find_usage(key)          namespace neighbours, UI type/tags, matching terms
  lookup_glossary(term)    termbase entry: zh, notes, do-not-translate, forbidden
  retranslate(context)     a fresh Claude draft that uses the context it gathered
  check(candidate)         placeholder / termbase / punctuation checks
  submit(candidate)        counts as an attempt: checks + fresh judge verdict
  escalate(reason)         gives up: writes an escalation for a human
"""
import csv
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, SCHEMA_FILE, EXPORT_DIR, ROOT, ANTHROPIC_MODEL, SPOT_CHECK_MAX_SEVERITY
from common import token_check, locale_check, ask, _claude
from terms import load_terms, matching_terms, prompt_block, term_adherence

MAX_ATTEMPTS = 2
MAX_TOOL_CALLS = 10
FULL_EN = ROOT / "data" / "string_pool" / "excalidraw_en_full.json"

_spec = importlib.util.spec_from_file_location("judge", Path(__file__).with_name("05_llm_judge.py"))
judge_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(judge_mod)

TOOLS = [
    {"name": "find_usage", "description": "Where the key is used: neighbouring keys in the same UI namespace with their English text, the UI type and tags, and glossary terms found in the source.",
     "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
    {"name": "lookup_glossary", "description": "Look up an English term in the approved EN->zh-CN termbase.",
     "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}},
    {"name": "retranslate", "description": "Get a fresh draft translation that takes the context you gathered into account. Does not count as an attempt.",
     "input_schema": {"type": "object", "properties": {"context": {"type": "string", "description": "What you learned: where the string appears, its meaning, constraints."}}, "required": ["context"]}},
    {"name": "check", "description": "Run the deterministic checks (placeholders/markup, termbase, Chinese punctuation) on a candidate. Free.",
     "input_schema": {"type": "object", "properties": {"candidate": {"type": "string"}}, "required": ["candidate"]}},
    {"name": "submit", "description": f"Submit a candidate as a repair attempt (max {MAX_ATTEMPTS}). Returns the checks and a fresh judge verdict. Accepted only if all checks pass and severity <= {SPOT_CHECK_MAX_SEVERITY}.",
     "input_schema": {"type": "object", "properties": {"candidate": {"type": "string"}}, "required": ["candidate"]}},
    {"name": "escalate", "description": "Hand the string to a human with a short reason, when you cannot fix it or the source itself is the problem.",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
]

SYSTEM = """You repair one machine-translated software UI string (English -> Simplified Chinese) for the Excalidraw whiteboard app.
Work step by step with the tools: understand where the string is used, check the glossary, then fix the translation.
Rules: keep every placeholder ({{x}}) and tag (<x>...</x>) exactly as in the source; use the approved glossary terms;
use full-width Chinese punctuation; keyboard key names stay as printed. Keep UI labels short.
You may submit at most %d candidates. If the problem is in the English source, or you cannot reach an acceptable
translation, escalate with a clear reason. Do not explain at length; act.""" % MAX_ATTEMPTS


def checks(sid, source, cand):
    tok = token_check(source, cand)
    loc = locale_check(cand)
    term = term_adherence(source, cand, sid)
    problems = []
    if not tok["token_ok"]:
        problems.append("placeholder: " + tok["token_detail"])
    if term["term_detail"]:
        problems.append("terminology: " + term["term_detail"])
    if not loc["locale_ok"]:
        problems.append("punctuation: " + loc["locale_detail"])
    return problems


class Repair:
    def __init__(self, con, run, sid, source, mt, sev, route, meta, full_en):
        self.con, self.run, self.sid, self.source = con, run, sid, source
        self.mt, self.sev, self.route, self.meta, self.full_en = mt, sev, route, meta, full_en
        self.attempts, self.calls, self.result, self.best = 0, 0, None, None

    def log(self, tool, inp, out):
        self.con.execute("INSERT INTO agent_steps (agent_run, string_id, step, tool, tool_input, tool_output) VALUES (?,?,?,?,?,?)",
                         (self.run, self.sid, self.calls, tool, json.dumps(inp, ensure_ascii=False), out))

    def tool(self, name, inp):
        if name == "find_usage":
            ns = self.sid.rsplit(".", 1)[0]
            near = {k: v for k, v in self.full_en.items() if k.startswith(ns + ".") and k != self.sid}
            out = {"key": self.sid, "ui_type": self.meta.get("stratum"), "tags": self.meta.get("tags"),
                   "namespace_neighbours": dict(list(near.items())[:15]),
                   "glossary_terms_in_source": [{"en": t["en"], "zh": t["zh"], "note": t["note"]} for t in matching_terms(self.source)]}
        elif name == "lookup_glossary":
            q = inp.get("term", "").lower()
            hits = [t for t in load_terms() if q and (q == t["en"].lower() or q in t["en"].lower())]
            out = [{"en": t["en"], "zh": t["zh"], "do_not_translate": t["dnt"], "note": t["note"],
                    "forbidden": t["forbidden"]} for t in hits[:5]] or "no termbase entry"
        elif name == "retranslate":
            prompt = (f"Translate this Excalidraw UI string into Simplified Chinese. Output only the translation.\n"
                      f"Keep placeholders and tags exactly. Use full-width Chinese punctuation.\n"
                      f"Context: {inp.get('context', '')}\n\n{prompt_block(self.source)}String: {self.source}")
            out = ask(prompt, max_tokens=400)
        elif name == "check":
            p = checks(self.sid, self.source, inp.get("candidate", ""))
            out = {"passed": not p, "problems": p}
        elif name == "submit":
            if self.attempts >= MAX_ATTEMPTS:
                out = {"refused": f"attempt limit ({MAX_ATTEMPTS}) reached: escalate"}
            else:
                self.attempts += 1
                cand = inp.get("candidate", "")
                p = checks(self.sid, self.source, cand)
                verdict = judge_mod.judge_one({"source_text": self.source, "mt_text": cand,
                                               "string_id": self.sid, "engine": "agent"})
                ok = not p and verdict["severity"] <= SPOT_CHECK_MAX_SEVERITY
                if self.best is None or verdict["severity"] < self.best[1]:
                    self.best = (cand, verdict["severity"])
                out = {"accepted": ok, "attempt": self.attempts, "problems": p, "judge": verdict}
                if ok:
                    self.result = ("repaired", cand, verdict["severity"], verdict.get("rationale", ""))
        elif name == "escalate":
            self.result = ("escalated", self.best[0] if self.best else None,
                           self.best[1] if self.best else None, inp.get("reason", ""))
            out = "escalated to a human"
        else:
            out = f"unknown tool {name}"
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        self.log(name, inp, text)
        return text

    def run_agent(self):
        messages = [{"role": "user", "content":
                     f"Key: {self.sid}\nSource: {self.source}\nCurrent translation: {self.mt}\n"
                     f"Why it was flagged: route={self.route}, judge severity={self.sev}, "
                     f"failed checks={checks(self.sid, self.source, self.mt) or 'none'}"}]
        while self.result is None:
            if self.calls >= MAX_TOOL_CALLS:
                self.result = ("escalated", self.best[0] if self.best else None,
                               self.best[1] if self.best else None, f"tool-call limit ({MAX_TOOL_CALLS}) reached")
                break
            kwargs = {"thinking": {"type": "between_tools"}} if ANTHROPIC_MODEL.startswith("claude-sonnet-5-5") else {}
            msg = _claude().messages.create(model=ANTHROPIC_MODEL, max_tokens=1500, system=SYSTEM,
                                            tools=TOOLS, messages=messages, **kwargs)
            messages.append({"role": "assistant", "content": msg.content})
            uses = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
            if not uses:
                self.result = ("escalated", self.best[0] if self.best else None,
                               self.best[1] if self.best else None, "agent stopped without a repair")
                break
            results = []
            for u in uses:
                self.calls += 1
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": self.tool(u.name, u.input)})
                if self.result is not None:
                    break
            messages.append({"role": "user", "content": results})
            if self.attempts >= MAX_ATTEMPTS and self.result is None:
                self.result = ("escalated", self.best[0] if self.best else None,
                               self.best[1] if self.best else None, f"{MAX_ATTEMPTS} attempts without an accepted candidate")
        return self.result


def main():
    con = sqlite3.connect(DB_PATH)
    con.executescript(Path(SCHEMA_FILE).read_text(encoding="utf-8"))
    full_en = json.loads(FULL_EN.read_text(encoding="utf-8"))
    meta = {}
    with open(ROOT / "data" / "reference_worksheet.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            meta[r["string_id"]] = r
    q = """SELECT r.string_id, s.source_text, r.mt_text, r.severity, r.route FROM routes r
           JOIN source_strings s ON s.string_id = r.string_id
           WHERE r.id IN (SELECT MAX(id) FROM routes GROUP BY string_id)"""
    rows = con.execute(q).fetchall()
    keys = sys.argv[1:]
    rows = [r for r in rows if (r[0] in keys if keys else r[4] in ("repair", "mandatory_review"))]
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    esc = []
    for sid, source, mt, sev, route in rows:
        rep = Repair(con, run, sid, source, mt, sev, route, meta.get(sid, {}), full_en)
        try:
            outcome, cand, sev_after, reason = rep.run_agent()
        except Exception as e:  # an API failure never counts as a repair
            outcome, cand, sev_after, reason = "escalated", None, None, f"agent error: {e}"
        con.execute("""INSERT INTO agent_outcomes (agent_run, string_id, route_before, mt_before, severity_before,
                       outcome, candidate, severity_after, attempts, reason) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (run, sid, route, mt, sev, outcome, cand, sev_after, rep.attempts, reason))
        con.commit()
        print(f"[agent] {sid}: {outcome} after {rep.attempts} attempt(s), {rep.calls} tool calls | "
              f"severity {sev} -> {sev_after} | {cand or '-'} | {reason}")
        if outcome == "escalated":
            esc.append((sid, source, mt, cand, reason))
    if esc:
        EXPORT_DIR.mkdir(exist_ok=True)
        lines = [f"# Escalations from the repair agent ({run})", ""]
        for sid, source, mt, cand, reason in esc:
            lines += [f"## `{sid}`", f"- Source: {source}", f"- MT: {mt}", f"- Best agent attempt: {cand or '-'}",
                      f"- Reason: {reason}", ""]
        (EXPORT_DIR / "escalations.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"[agent] {len(esc)} escalation(s) written to data/exports/escalations.md "
              f"(open them as GitHub issues with: gh issue create --title ... --body-file ...)")
    # How close did the agent get to what the human reviewer approved in the TMS?
    final = dict(con.execute("""SELECT string_id, final_text FROM review_edits
                                WHERE id IN (SELECT MAX(id) FROM review_edits GROUP BY string_id)"""))
    if final:
        from importlib import import_module
        dist = import_module("crowdin_pull_review").edit_distance
        cmp = [(sid, o[0], o[1]) for sid, *o in con.execute(
            "SELECT string_id, mt_before, candidate FROM agent_outcomes WHERE agent_run = ?", (run,)) if sid in final]
        for sid, before, cand in cmp:
            b = dist(before or "", final[sid])
            a = dist(cand, final[sid]) if cand else None
            print(f"[agent vs reviewer] {sid}: distance to approved text {b:.2f} -> "
                  f"{'-' if a is None else f'{a:.2f}'}  (approved: {final[sid]})")
    n = len(rows)
    rep_n = n - len(esc)
    print(f"[agent] {rep_n}/{n} repaired, {len(esc)} escalated. Repaired strings still go to full human review.")


if __name__ == "__main__":
    main()
