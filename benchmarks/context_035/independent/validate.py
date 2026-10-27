import json, re, collections
L = [json.loads(l) for l in open("questions.jsonl", encoding="utf-8")]
assert len(L) == 300, len(L)
cats = collections.Counter(x["category"] for x in L)
print(cats)
ids = set()
feats = collections.Counter()
longn = 0
bad = 0
def wi(t, s):
    return re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", t, re.I) is not None
for x in L:
    assert x["id"] not in ids; ids.add(x["id"])
    h = x["history"]
    assert 5 <= len(h) <= 50, (x["id"], len(h))
    for i, m in enumerate(h):
        assert m["role"] == ("user" if i % 2 == 0 else "assistant")
    assert h[-1]["role"] == "assistant"
    c = x["criteria"]
    assert set(c) == {"any", "none", "clarify", "no_clarify", "abstain"}
    for f in x["features"]: feats[f] += 1
    if len(h) >= 40: longn += 1
    text = " ".join(m["content"] for m in h)
    if not c["abstain"] and x["category"] != "reasoning" and "multistep" not in x["features"]:
        for g in c["any"]:
            if not any(wi(text, s) for s in g):
                # allow substring (e.g. 4pm variants)
                if not any(s.lower() in text.lower() for s in g):
                    print("MISSING", x["id"], g); bad += 1
    if c["abstain"]:
        assert c["any"] == [] and c["none"]
        for s in c["none"]:
            if not wi(text, s): print("DISTRACTOR NOT IN TEXT", x["id"], s); bad += 1
print(feats, "long", longn, "bad", bad)
