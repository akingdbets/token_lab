"""recall 6턴의 근거 인용 잔존 표: query_select·hybrid(로컬), LongLLMLingua(로컬 CPU gpt2, Colab run2 0.5B/1.5B/7B).

python docs/experiments/feasibility/quality_table.py
"""
import json
from collections import defaultdict

from common import (OUT, count_tokens, evidence_checks, history_and_current, history_tokens, load_scenario,
                    split_turns, text_of)

agg = defaultdict(lambda: {"n": 0, "exact": 0, "cov": 0, "tok": 0, "rows": 0})
recall_pts = set()
for sid in ("v2_01_auth_switch", "v2_02_response_design"):
    for t in load_scenario(sid)["turns"]:
        if t["turn_type"] == "recall":
            recall_pts.add((sid, t["turn"]))


def add(name, r, checks, tok):
    a = agg[(name, r)]
    a["rows"] += 1
    a["tok"] += tok
    for c in checks:
        if not c["in_raw"]:
            continue
        a["n"] += 1
        a["exact"] += c["exact"]
        a["cov"] += c["cov"] >= 0.8


for x in json.load(open(OUT / "hybrid_rows.json", encoding="utf-8")):
    if (x["scenario"], x["turn"]) in recall_pts and x["method"] in ("query_select", "hybrid_q0"):
        add(x["method"], x["ratio"], x["checks"], x["comp_tokens"])
d = json.load(open(OUT / "ll_quality_gpt2.json", encoding="utf-8"))
for x in d["rows"]:
    add("LL gpt2 (CPU)", x["ratio"], x["checks"], x["comp_tokens"])

cache = {}
for p in sorted(OUT.glob("ll_outputs_*.jsonl")):
    name = "LL " + p.stem.removeprefix("ll_outputs_Qwen2.5-") + " (T4)"
    for line in p.open(encoding="utf-8"):
        x = json.loads(line)
        key = (x["scenario"], x["turn"])
        if key not in cache:
            scn = load_scenario(x["scenario"])
            past, _ = history_and_current(scn, x["turn"])
            cache[key] = (scn, past)
        scn, past = cache[key]
        recent = split_turns(past)[-1]
        msgs = ([{"role": "user", "content": "<compressed_history>\n" + x["compressed_prompt"] + "\n</compressed_history>"}]
                if x["compressed_prompt"] else []) + recent
        add(name, x["ratio"], evidence_checks(scn, x["turn"], text_of(past), text_of(msgs)),
            history_tokens(msgs, count_tokens))

order = ["query_select", "hybrid_q0", "LL gpt2 (CPU)", "LL 0.5B (T4)", "LL 1.5B (T4)", "LL 7B (T4)"]
print("| 방법 | " + " | ".join(f"r={r} 그대로 / 80%이상 (평균 토큰)" for r in (0.25, 0.5, 0.75)) + " |")
print("|---|---|---|---|")
for m in order:
    cells = []
    for r in (0.25, 0.5, 0.75):
        a = agg.get((m, r))
        cells.append("-" if not a else f"{a['exact']}/{a['n']} · {a['cov']}/{a['n']} ({a['tok'] / a['rows']:.0f})")
    print(f"| {m} | " + " | ".join(cells) + " |")
