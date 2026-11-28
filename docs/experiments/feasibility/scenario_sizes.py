"""정식 시나리오 20개의 턴별 기록 토큰과 query_select 조각 수 (전체 예상 시간 계산용). 파일만 읽는다."""
import json

from common import DATA, OUT, count_tokens, history_and_current, history_tokens, split_turns
from multiturn.history_compressors.budget import _units_of_turn

rows, unique = [], set()
for f in sorted(DATA.glob("v2_*.json")):
    scn = json.loads(f.read_text(encoding="utf-8"))
    n_turns = len(scn["turns"])
    past, _ = history_and_current(scn, n_turns - 1)
    turns = split_turns(past)
    for i, t in enumerate(turns):
        for u in _units_of_turn(i, t):
            unique.add(u["text"])
    # 각 턴 k 의 기록 토큰 (턴 0 은 기록 없음)
    sizes = []
    for k in range(1, n_turns):
        p, _ = history_and_current(scn, k)
        sizes.append(history_tokens(p, count_tokens))
    rows.append({"scenario": scn["scenario_id"], "turns": n_turns, "hist_tokens": sizes})
uniq_tokens = sum(count_tokens(t) for t in unique)
out = {"scenarios": rows, "unique_units": len(unique), "unique_unit_tokens": uniq_tokens}
(OUT / "scenario_sizes.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(len(rows), sum(r["turns"] for r in rows), "compress points", sum(len(r["hist_tokens"]) for r in rows),
      "max hist", max(max(r["hist_tokens"]) for r in rows), "mean hist",
      sum(sum(r["hist_tokens"]) for r in rows) / sum(len(r["hist_tokens"]) for r in rows),
      "unique units", len(unique), uniq_tokens)
