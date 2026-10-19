"""
기존 run 에 기억 의존 의심(memory_suspect)을 소급 계산 (API 호출 없음)

experiment.py 는 새 run 의 trial 마다 memory_suspect 를 남긴다. 그 전에 돌린 run 은 저장된 압축 문맥
(contexts/<qid>.<압축기>.md) 과 평가셋의 answer·key_entities 로 여기서 계산한다.

    EVAL_DIR=data/evalsets/claude-v1 python src/memory_suspect.py results/runs/<run_id>

memory_suspect = 압축 문맥에 정답 핵심어가 없는데(experiment.answer_core_in_context) answer_accuracy >= 0.5
결과: 압축기별 수·비율을 출력하고 <run>/memory_suspect.json 에 문항 목록과 함께 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import answer_core_in_context, load_items, memory_suspect


def main():
    ap = argparse.ArgumentParser(description="기존 run 에 memory_suspect 소급 계산")
    ap.add_argument("run_dir", help="results/runs/<run_id>")
    args = ap.parse_args()

    run = Path(args.run_dir)
    trials = [json.loads(l) for l in open(run / "trials.jsonl", encoding="utf-8") if l.strip()]
    items = {it["id"]: it for it in load_items("all", None, None)}
    out: dict[str, dict] = {}
    for t in trials:
        ctx_file = run / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
        if not ctx_file.exists():
            sys.exit(f"압축 문맥 파일이 없습니다: {ctx_file}")
        core = answer_core_in_context(ctx_file.read_text(encoding="utf-8"), items[t["qid"]])
        s = out.setdefault(t["compressor"], {"n": 0, "core_missing": 0, "memory_suspect": 0, "items": []})
        s["n"] += 1
        s["core_missing"] += not core
        if memory_suspect(core, t.get("answer_accuracy")):
            s["memory_suspect"] += 1
            s["items"].append({"qid": t["qid"], "qtype": t["qtype"], "answer_accuracy": t["answer_accuracy"],
                               "response": t["response"]})
    for s in out.values():
        s["memory_suspect_rate"] = round(s["memory_suspect"] / s["n"], 4)
    (run / "memory_suspect.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for c, s in out.items():
        print(f"{c:<14} n={s['n']}  문맥에 핵심어 없음 {s['core_missing']}  기억 의존 의심 {s['memory_suspect']} "
              f"({s['memory_suspect_rate']:.1%})  {[x['qid'] for x in s['items']]}")


if __name__ == "__main__":
    main()
