import json, re, os, collections
os.chdir(os.path.dirname(os.path.abspath(__file__)))
lines = open("questions.jsonl", encoding="utf-8").read().split("\n")
assert lines[-1] == ""
lines = lines[:-1]
errs = []
if len(lines) != 400: errs.append(f"lines {len(lines)}")
items = [json.loads(l) for l in lines]
ids = set()
cnt = collections.Counter(); longc = collections.Counter(); fc = collections.Counter()
EXP = {"memory": 50, "update": 50, "reference": 40, "conflict": 50, "planning": 50, "reasoning": 80, "unsupported": 80}
FEATS = {"passive", "negation", "indirect", "unusual_structure", "multistep", "paraphrase", "long"}
def has(txt, s):
    return re.search(r"(?<![\w])" + re.escape(s) + r"(?![\w])", txt, re.I) is not None
for it in items:
    i = it["id"]
    if i in ids: errs.append("dup " + i)
    ids.add(i)
    c = it["category"]; cnt[c] += 1
    h = it["history"]
    n = len(h)
    for f in it["features"]:
        fc[f] += 1
        if f not in FEATS: errs.append(f"{i} bad feat {f}")
    isl = "long" in it["features"]
    if isl:
        longc[c] += 1
        if not 100 <= n <= 200: errs.append(f"{i} long len {n}")
    else:
        if not 5 <= n <= 50: errs.append(f"{i} short len {n}")
    for j, m in enumerate(h):
        if m["role"] != ("user" if j % 2 == 0 else "assistant"): errs.append(f"{i} role {j}")
    if h[-1]["role"] != "assistant": errs.append(i + " end")
    cr = it["criteria"]
    text = " ".join(m["content"] for m in h)
    if cr["abstain"]:
        if cr["any"] != [] or not cr["none"]: errs.append(i + " abstain shape")
        for s in cr["none"]:
            if not has(text, s): errs.append(f"{i} none not in hist {s}")
    else:
        anys = cr["any"]
        yn = any(g in (["yes"], ["no"]) for g in anys)
        if c != "reasoning" and not yn and it["id"] and "How many steps" not in it["question"]:
            for g in anys:
                if not any(has(text, s) for s in g): errs.append(f"{i} any {g} not in hist")
        for g in anys:
            for s in g:
                if s in cr["none"]: errs.append(f"{i} any/none overlap {s}")
        if not anys: errs.append(i + " empty any")
    if cr["clarify"] and cr["no_clarify"]: errs.append(i + " both")
    if c == "conflict" and not (cr["clarify"] or cr["no_clarify"]): errs.append(i + " conflict flags")
    # facts duplicated in history among user messages?
    us = [m["content"] for m in h if m["role"] == "user"]
    if len(set(us)) != len(us): errs.append(i + " dup user msg")
for c, n in EXP.items():
    if cnt[c] != n: errs.append(f"count {c} {cnt[c]}")
    if longc[c] < 0.25 * n: errs.append(f"long {c} {longc[c]}")
print(errs[:60], len(errs))
print(dict(cnt)); print(dict(longc)); print(dict(fc))
cl = sum(1 for it in items if it["criteria"]["clarify"]); nc = sum(1 for it in items if it["criteria"]["no_clarify"])
print("clarify", cl, "no_clarify", nc)
