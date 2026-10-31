"""
기존 run 에 기억 의존 의심(memory_suspect)을 소급 계산 (API 호출 없음)

experiment.py 는 새 run 의 trial 마다 memory_suspect 를 남긴다. 그 전에 돌린 run 은 저장된 압축 문맥
(contexts/<qid>.<압축기>.md) 과 평가셋의 answer·key_entities 로 여기서 계산한다.

    EVAL_DIR=data/evalsets/claude-v1 python src/memory_suspect.py results/runs/<run_id>

memory_suspect = 압축 문맥에 정답 핵심어가 없는데(experiment.answer_core_in_context) answer_accuracy >= 0.5
문맥 검사는 정규화 매칭(CORE_MATCH_VERSION)이고, 비교용으로 이전 방식(단어 연속 일치, *_strict)도 함께 계산한다.
결과: 압축기별 "이전 수 -> 새 수"와, 이전 방식으로 의심이던 문항마다 정규화로 바뀌었는지(문맥에서 찾은 구절)
표로 출력하고 <run>/memory_suspect.json 에 문항 목록과 함께 쓴다. 정규화로 안 바뀐 문항은 표현이 바뀐(paraphrase)
경우일 수 있으니 사람이 분류한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import CORE_MATCH_VERSION, answer_core_in_context_strict, core_matches, load_items, memory_suspect


def main():
    ap = argparse.ArgumentParser(description="기존 run 에 memory_suspect 소급 계산")
    ap.add_argument("run_dir", help="results/runs/<run_id>")
    args = ap.parse_args()

    run = Path(args.run_dir)
    trials = [json.loads(l) for l in open(run / "trials.jsonl", encoding="utf-8") if l.strip()]
    items = {it["id"]: it for it in load_items("all", None, None)}
    out: dict[str, dict] = {}
    changed = []
    for t in trials:
        ctx_file = run / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
        if not ctx_file.exists():
            sys.exit(f"압축 문맥 파일이 없습니다: {ctx_file}")
        ctx, item = ctx_file.read_text(encoding="utf-8"), items[t["qid"]]
        core, hits = core_matches(ctx, item)
        core_strict = answer_core_in_context_strict(ctx, item)
        s = out.setdefault(t["compressor"], {"n": 0, "core_missing": 0, "memory_suspect": 0, "items": [],
                                             "core_missing_strict": 0, "memory_suspect_strict": 0})
        s["n"] += 1
        s["core_missing"] += not core
        s["core_missing_strict"] += not core_strict
        sus, sus_strict = memory_suspect(core, t.get("answer_accuracy")), memory_suspect(core_strict, t.get("answer_accuracy"))
        s["memory_suspect_strict"] += sus_strict
        if sus:
            s["memory_suspect"] += 1
            s["items"].append({"qid": t["qid"], "qtype": t["qtype"], "answer_accuracy": t["answer_accuracy"],
                               "response": t["response"]})
        if sus or sus_strict:
            changed.append({"qid": t["qid"], "compressor": t["compressor"], "answer": item["answer"],
                            "strict": sus_strict, "normalized": sus, "found": hits,
                            "response": t["response"].strip()[:60]})
    for s in out.values():
        s["memory_suspect_rate"] = round(s["memory_suspect"] / s["n"], 4)
        s["memory_suspect_strict_rate"] = round(s["memory_suspect_strict"] / s["n"], 4)
    res = {"core_match_version": CORE_MATCH_VERSION, "compressors": out, "suspect_items": changed}
    (run / "memory_suspect.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    print(f"## {run.name}  ({CORE_MATCH_VERSION})\n")
    print("| 압축기 | n | 이전 memory_suspect | 새 memory_suspect |\n|---|---|---|---|")
    for c, s in out.items():
        print(f"| {c} | {s['n']} | {s['memory_suspect_strict']} | {s['memory_suspect']} |")
    if changed:
        print("\n| qid | 압축기 | 정답 | 결과 | 문맥에서 찾은 구절 | 답변 |\n|---|---|---|---|---|---|")
        for x in changed:
            status = ("의심 해제" if x["strict"] and not x["normalized"] else
                      "정규화로 안 바뀜" if x["strict"] else "새로 의심")
            found = " / ".join(f"`{h}`" for h in x["found"]) or "-"
            print(f"| {x['qid']} | {x['compressor']} | {cell(x['answer'])} | {status} | {cell(found)} "
                  f"| {cell(x['response'])} |")


if __name__ == "__main__":
    main()
