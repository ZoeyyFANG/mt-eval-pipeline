"""
Step 5: LLM-as-a-Judge (a reference-free QE signal).

Scores each MT output against an MQM-lite rubric focused on whether
the error breaks what the user is trying to do, not just whether the
sentence is linguistically perfect. It sees only source + MT, never
the reference, so it can route live strings. Whether it can be trusted
is tested offline against human labels (scripts/analyze_qe.py).
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MT_OUTPUTS_FILE, LLM_JUDGE_FILE, MQM_ERROR_TYPES
from common import ask_json, _stable_int

JUDGE_PROMPT = """You are a Chinese localization QA judge for software UI strings, using an MQM-inspired rubric.

Source (English): {source}
Translation (Simplified Chinese): {mt}

Error types to consider: {error_types}
Placeholders such as {{{{count}}}} and tags such as <link>…</link> must appear unchanged in the translation.

Score severity 1-6 based on IMPACT ON THE USER'S TASK, not just linguistic correctness:
1 = perfect, no issue
2 = trivial style preference, no user impact
3 = minor error, cosmetic, user still understands and completes the task
4 = noticeable error, user may hesitate or misread, task still completable
5 = major error, likely to cause user mistakes or confusion in the UI
6 = critical error, breaks the function / gives wrong instruction / placeholder mismatch

Respond ONLY with compact JSON:
{{"error_type": "<one of the listed types or 'none'>", "severity": <1-6>, "rationale": "<one short sentence>"}}
"""


def mock_judge(item):
    if not item.get("token_ok", True):
        return {"error_type": "placeholder_mismatch", "severity": 6, "rationale": "mock"}
    sev = 1 + _stable_int(item["engine"] + item["string_id"], 5)
    return {"error_type": "none" if sev <= 2 else "fluency", "severity": sev, "rationale": "mock"}


def judge_one(item):
    result = ask_json(
        JUDGE_PROMPT.format(source=item["source_text"], mt=item["mt_text"],
                            error_types=", ".join(MQM_ERROR_TYPES)),
        max_tokens=250,
        mock_reply=lambda _: json.dumps(mock_judge(item)),
    )
    sev = int(result.get("severity", 0))
    if not 1 <= sev <= 6:
        raise ValueError(f"severity out of range: {result}")
    if result.get("error_type") not in MQM_ERROR_TYPES:
        result["error_type"] = "accuracy" if sev >= 4 else "none"
    result["severity"] = sev
    return result


def main():
    outputs = json.loads(Path(MT_OUTPUTS_FILE).read_text(encoding="utf-8"))
    judged, failed = [], 0
    for item in outputs:
        try:
            result = judge_one(item)
        except Exception as e:
            failed += 1
            print(f"[judge] FAILED {item['string_id']} / {item['engine']}: {e}")
            continue
        judged.append({"string_id": item["string_id"], "engine": item["engine"], **result})
        print(f"[judge] {item['string_id']} / {item['engine']}: "
              f"severity {result['severity']} ({result['error_type']})")
    Path(LLM_JUDGE_FILE).write_text(
        json.dumps(judged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[judge] judged {len(judged)}, failed {failed}.")


if __name__ == "__main__":
    main()
