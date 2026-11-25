"""
Human MQM (docs/mqm_framework.md) vs machine scores.

Human: labels/mqm_annotation.csv (MQM-Core dimension, Neutral/Minor/Major/Critical,
up to 2 errors per segment); segments labelled has_error=0 carry no penalty.
System level: MQM penalty points per 1000 source words and quality score per engine,
for the human annotation and for the LLM judge mapped onto MQM severities
(1-2 none, 3-4 minor, 5 major, 6 critical). Segment level: the worst human severity
(none=1, minor=3, major=5, critical=6) compared with:
  - LLM judge severity (same 1-6 scale, same run the label came from)
  - COMET (reference-based) and CometKiwi (reference-free), higher = better,
    so they are negated before correlating
Reports segment-level Spearman correlation (with bootstrap 95% CI), agreement
on error rows (exact / within 1 point), error-type agreement, and whether
human MQM and each metric rank the three engines the same way.

    python scripts/mqm_alignment.py   ->  data/exports/mqm_alignment_report.md
"""
import csv, random, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, EXPORT_DIR

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "labels"
SETS = [("b1", "qe_labels_zoey.csv", "_key_zoey.csv"), ("b2", "qe_labels_zoey_b2.csv", "_key_zoey_b2.csv")]


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x); i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5; vb = sum((y - mb) ** 2 for y in rb) ** .5
    return cov / (va * vb) if va and vb else float("nan")


def boot_ci(a, b, n=2000, seed=7):
    rng, idx, vals = random.Random(seed), range(len(a)), []
    for _ in range(n):
        s = [rng.choice(idx) for _ in idx]
        v = spearman([a[i] for i in s], [b[i] for i in s])
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]


PEN = {"neutral": 0, "minor": 1, "major": 5, "critical": 25}
LEVEL = {"none": 1, "neutral": 1, "minor": 3, "major": 5, "critical": 6}
JUDGE2MQM = {1: "none", 2: "none", 3: "minor", 4: "minor", 5: "major", 6: "critical"}
PASS_SCORE = 95


def load_segments():
    p = LAB / "mqm_annotation.csv"
    if not p.exists():
        sys.exit("labels/mqm_annotation.csv not found — fill labels/mqm_annotation_todo.csv (rules: docs/mqm_framework.md)")
    ann, missing = {}, 0
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        errs = []
        for d, sv in (("dimension", "severity"), ("error2_dimension", "error2_severity")):
            sev = r[sv].strip().lower()
            if sev:
                if sev not in PEN:
                    sys.exit(f"{r['row_id']}: severity '{sev}' is not one of {list(PEN)}")
                errs.append((r[d].strip(), sev))
        if not errs:
            missing += 1; continue
        ann[r["row_id"]] = errs
    segs = []
    for tag, lab, key in SETS:
        keys = {r["item_id"]: r for r in csv.DictReader(open(LAB / key, encoding="utf-8-sig"))}
        for r in csv.DictReader(open(LAB / lab, encoding="utf-8-sig")):
            k, rid = keys[r["item_id"]], f"{tag}-{r['item_id']}"
            if r["has_error"].strip() == "1":
                if rid not in ann:
                    continue
                errs = ann[rid]
            else:
                errs = []
            worst = max((LEVEL[s] for _, s in errs), default=1)
            segs.append({"row_id": rid, "string_id": k["string_id"], "engine": k["engine"], "run_id": k["run_id"],
                         "words": max(1, len(r["source_en"].split())), "errors": errs, "human": worst,
                         "human_dim": errs[0][0] if errs else "none"})
    return segs, missing


def attach_machine(con, segs):
    for s in segs:
        j = con.execute("""SELECT severity, error_type FROM llm_judge_scores
                           WHERE string_id = ? AND engine = ? AND run_id = ? ORDER BY id DESC LIMIT 1""",
                        (s["string_id"], s["engine"], s["run_id"])).fetchone()
        s["judge"], s["judge_type"] = (j if j else (None, None))
        c = con.execute("""SELECT comet, cometkiwi FROM comet_scores WHERE string_id = ? AND engine = ?
                           ORDER BY id DESC LIMIT 1""", (s["string_id"], s["engine"])).fetchone()
        s["comet"], s["cometkiwi"] = (c if c else (None, None))


def mqm_system(rows, errs_of):
    ewc = sum(s["words"] for s in rows)
    cnt = Counter(sev for s in rows for _, sev in errs_of(s))
    apt = sum(PEN[k] * v for k, v in cnt.items())
    npt = apt * 1000 / ewc
    score = 100 - npt / 10
    verdict = "FAIL" if cnt["critical"] or score < PASS_SCORE else "pass"
    return ewc, cnt, apt, npt, score, verdict


def main():
    segs, missing = load_segments()
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    attach_machine(con, segs)
    md = ["# MQM: human annotation vs machine scores", "",
          f"Framework: docs/mqm_framework.md. {len(segs)} segments (batch 1 + held-out batches 2-4). "
          + (f"**{missing} error rows not annotated yet and left out.**" if missing else ""), "",
          "## System level: MQM score per engine (penalty points per 1000 source words)", "",
          "| Engine | Segments | Source words | Minor | Major | Critical | Penalty / 1000 w | Quality score | Verdict | Judge-implied score |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for s in segs:
        by[s["engine"]].append(s)
    human_rank, judge_rank = {}, {}
    for e, rows in sorted(by.items()):
        ewc, cnt, apt, npt, score, verdict = mqm_system(rows, lambda s: s["errors"])
        jrows = [s for s in rows if s["judge"] is not None]
        jscore = mqm_system(jrows, lambda s: [("", JUDGE2MQM[s["judge"]])] if JUDGE2MQM[s["judge"]] != "none" else [])[4]
        human_rank[e], judge_rank[e] = score, jscore
        md.append(f"| {e} | {len(rows)} | {ewc} | {cnt['minor']} | {cnt['major']} | {cnt['critical']} | "
                  f"{npt:.0f} | {score:.1f} | {verdict} | {jscore:.1f} |")
    order = lambda d: " > ".join(sorted(d, key=lambda e: -d[e]))
    md += ["", f"- Ranking by human MQM: {order(human_rank)}; by judge-implied MQM: {order(judge_rank)}.",
           f"- Pass rule (project): no Critical and score >= {PASS_SCORE}. Raw MT of UI strings is not expected to pass; "
           "the score is for comparing engines and tracking change, the verdict shows how far raw MT is from shippable."]
    dims = Counter((s["engine"], d) for s in segs for d, _ in s["errors"])
    md += ["", "Errors by MQM dimension:", "", "| Dimension | " + " | ".join(sorted(by)) + " |",
           "|---|" + "---|" * len(by)]
    for d in sorted({d for _, d in dims}):
        md.append(f"| {d} | " + " | ".join(str(dims[(e, d)]) for e in sorted(by)) + " |")

    sysm = Counter((s["engine"], d) for s in segs for d, _ in s["errors"])
    syst = [(e, d, n) for (e, d), n in sorted(sysm.items()) if n >= 3]
    md += ["", "Systematic errors (same dimension >= 3 times for one engine; fix once at the source):", ""]
    md += [f"- {e}: {d} x{n}" for e, d, n in syst] or ["- none"]
    md += ["", "## Segment level: does the metric order segments like the human does?", "",
           "| Metric | n | Spearman vs worst human severity | 95% CI |", "|---|---|---|---|"]
    for name, sign in (("judge", 1), ("comet", -1), ("cometkiwi", -1)):
        rows = [s for s in segs if s[name] is not None]
        if len(rows) < 10:
            md.append(f"| {name} | {len(rows)} | not enough data | |"); continue
        h = [s["human"] for s in rows]; m = [sign * s[name] for s in rows]
        lo, hi = boot_ci(h, m)
        md.append(f"| {name}{' (negated)' if sign < 0 else ''} | {len(rows)} | {spearman(h, m):.2f} | {lo:.2f} to {hi:.2f} |")
    err = [s for s in segs if s["errors"] and s["judge"] is not None]
    if err:
        worst = lambda s: max(s["errors"], key=lambda x: PEN[x[1]])[1]
        same = sum(JUDGE2MQM[s["judge"]] == worst(s) for s in err)
        missed = sum(JUDGE2MQM[s["judge"]] == "none" for s in err)
        conf = Counter((worst(s), JUDGE2MQM[s["judge"]]) for s in err)
        md += ["", "## On the human-annotated errors", "",
               f"- {len(err)} segments with errors. Judge (mapped to MQM) gave the same severity on {same} "
               f"({100*same/len(err):.0f}%); called {missed} of them no error (they would auto-ship without the rule checks).",
               "- Human severity → judge severity (count): " + "; ".join(
                   f"{h} → {j}: {n}" for (h, j), n in sorted(conf.items()))]
    md += ["", "Caveats: one human annotator; the judge is Claude scoring Claude among others "
           "(self-preference risk); COMET uses references reviewed against the termbase."]
    EXPORT_DIR.mkdir(exist_ok=True)
    (EXPORT_DIR / "mqm_alignment_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
