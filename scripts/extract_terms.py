import sys, json, re, math, collections, csv
import spacy
from wordfreq import word_frequency
nlp = spacy.load("en_core_web_sm")
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data/string_pool/excalidraw_en_full.json"))
def flat(d, p=""):
    for k, v in d.items():
        kk = f"{p}.{k}" if p else k
        if isinstance(v, dict): yield from flat(v, kk)
        else: yield kk, v
items = list(flat(d))
clean = lambda t: re.sub(r"\{\{.*?\}\}|<[^>]+>", " ", t)
freq = collections.Counter(); docs = collections.defaultdict(set); ex = {}
total_tokens = 0
for key, text in items:
    doc = nlp(clean(text))
    total_tokens += len([t for t in doc if t.is_alpha])
    toks = list(doc)
    # POS patterns: (ADJ|NOUN|PROPN)* NOUN|PROPN, up to 3 tokens
    for i in range(len(toks)):
        for n in (1, 2, 3):
            span = toks[i:i+n]
            if len(span) < n: break
            if not all(t.is_alpha or "+" in t.text for t in span): continue
            if span[-1].pos_ not in ("NOUN", "PROPN"): continue
            if any(t.pos_ not in ("ADJ", "NOUN", "PROPN") for t in span[:-1]): continue
            if any(t.is_stop for t in span): continue
            lemma = " ".join(t.lemma_.lower() for t in span)
            freq[lemma] += 1; docs[lemma].add(key); ex.setdefault(lemma, (key, text))
rows = []
for term, f in freq.items():
    if len(docs[term]) < 2: continue
    words = term.split()
    gen = math.prod(max(word_frequency(w, "en"), 1e-7) for w in words) ** (1/len(words))
    local = f / total_tokens
    keyness = math.log2(local / gen)
    rows.append((term, f, len(docs[term]), round(keyness, 2), ex[term][0], ex[term][1][:90]))
rows.sort(key=lambda r: (-r[3] * math.log(1 + r[2])))
with open("data/terms/term_candidates.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(["candidate", "freq", "n_strings", "keyness_log2", "example_key", "example"]); w.writerows(rows)
print(len(rows), "candidates")
for r in rows[:90]: print(r[:4], r[4])
