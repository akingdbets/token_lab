"""recall 6턴 x 비율 3개 = 18건에서 압축기별 답변 정확도 비교 (gpt-6-luna 답변, fact_judge_v3 채점).

압축기
    none          원본 기록 (참고용 상한)
    query_select  기존 BM25 (multiturn.history_compressors.budget.select_history), 예산 = r x 원본 기록 토큰
    hybrid_q0     BM25 + bge-m3 (현재 질문만), 같은 예산. Ollama bge-m3 필요
    ll_<모델>     Colab 결과 results/feasibility/ll_outputs_<모델>.jsonl 의 compressed_prompt + 최근 1턴 원문

답변 설정은 closed_book_v2 와 같다: gpt-6-luna, reasoning_effort server_default, 출력 한도 4096, temperature 안 보냄,
지시문 mt_answer_v2. 채점: fact_judge_v3, per_fact, accept_alternatives. 주 정확도 = setup 태그를 뺀 key_fact 기준.
채점 질문은 replay 와 같이 turn["question"]. 과거 기록의 assistant 응답은 시나리오 정답(answer)으로 둔다 (실험 reference 궤적 아님).

python docs/experiments/feasibility/eval_compare.py                  # API 없이 메시지·토큰만 점검 (기본)
python docs/experiments/feasibility/eval_compare.py --run            # 답변·채점 호출 (끝난 건 건너뜀)
python docs/experiments/feasibility/eval_compare.py --report         # 표만 다시 출력
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict

from common import (OUT, RATIOS, SAMPLES, count_tokens, history_and_current, history_tokens, load_scenario,
                    question_of, split_turns)

ROWS = OUT / "eval_rows.jsonl"


def points():
    for sid in SAMPLES:
        scn = load_scenario(sid)
        for t in scn["turns"]:
            if t["turn_type"] == "recall":
                yield scn, t["turn"]


def ll_outputs():
    out = {}
    for p in sorted(OUT.glob("ll_outputs_*.jsonl")):
        arm = "ll_" + p.stem.removeprefix("ll_outputs_")
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            out[(arm, r["scenario"], r["turn"], r["ratio"])] = r["compressed_prompt"]
    return out


def build_arms(scn, k, r, ll):
    from multiturn.history_compressors.budget import select_history
    from hybrid import select_hybrid
    past, cur = history_and_current(scn, k)
    n = history_tokens(past, count_tokens)
    B = int(n * r)
    q = question_of(cur)
    arms = {"query_select": select_history(q, past, B, count_tokens)[0],
            "hybrid_q0": select_hybrid(q, past, B)[0]}
    recent = [m for m in split_turns(past)[-1]]
    for (arm, sid, kk, rr), cp in ll.items():
        if (sid, kk, rr) == (scn["scenario_id"], k, r):
            head = [{"role": "user", "content": "<compressed_history>\n" + cp + "\n</compressed_history>"}] if cp else []
            arms[arm] = head + recent
    return past, cur, n, B, arms


def done_keys():
    if not ROWS.exists():
        return set()
    return {(x["arm"], x["scenario"], x["turn"], x["ratio"], x["sample_idx"])
            for x in map(json.loads, ROWS.open(encoding="utf-8"))}


def report():
    if not ROWS.exists():
        print("결과 없음")
        return
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
    for x in map(json.loads, ROWS.open(encoding="utf-8")):
        a = agg[(x["arm"], x["ratio"])]
        a[0] += 1
        a[1] += x["main_accuracy"]
        a[2] += x["accuracy"]
        a[3] += x["history_tokens"]
        a[4] += x["not_found"]
    print("| 압축기 | 비율 | 건수 | 주 정확도 | 전체 정확도 | 평균 기록 토큰 | NOT FOUND |")
    print("|---|---|---|---|---|---|---|")
    for (arm, r), a in sorted(agg.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"| {arm} | {r} | {a[0]} | {a[1] / a[0]:.3f} | {a[2] / a[0]:.3f} | {a[3] / a[0]:.0f} | {a[4]} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--samples", type=int, default=1, help="조건당 답변 반복 수 (sample_idx 0..n-1)")
    ap.add_argument("--no-none", action="store_true", help="원본 기록(none) 조건을 뺀다")
    a = ap.parse_args()
    if a.report:
        return report()
    from multiturn.prompt import load_mt_prompt
    from multiturn.closed_book_v2 import _alternatives, main_accuracy
    prompt = load_mt_prompt("v2")
    ll = ll_outputs()
    print("Colab 결과:", sorted({k[0] for k in ll}) or "없음")
    if a.run:
        from grader import grade_answer_accuracy, is_not_found_answer
        from multiturn.closed_book_v2 import make_llms
        from multiturn.response_cache import CachedLLM
        answer_llm, judge_llm = make_llms()
        answer, judge = CachedLLM(answer_llm), judge_llm
    done = done_keys()
    plan = []
    for scn, k in points():
        for r in RATIOS:
            past, cur, n, B, arms = build_arms(scn, k, r, ll)
            if not a.no_none:
                arms = {"none": past, **arms}
            for arm, hist in arms.items():
                plan.append((scn, k, r, n, B, arm, hist, cur))
    print(f"조건 {len(plan)}개 x 반복 {a.samples} = {len(plan) * a.samples}건, 끝남 {len(done)}건")
    for scn, k, r, n, B, arm, hist, cur in plan:
        ht = history_tokens(hist, count_tokens)
        if not a.run:
            print(f"{scn['scenario_id'][:5]} t{k} r{r} {arm:<22} 기록 {ht:>6} / 원본 {n} (예산 {B})")
            continue
        t = scn["turns"][k]
        msgs = [{"role": "system", "content": prompt.system}] + hist + [{"role": "user", "content": cur}]
        for i in range(a.samples):
            key = (arm, scn["scenario_id"], k, r, i)
            if key in done:
                continue
            for attempt in range(6):            # 연결 끊김 등은 기다렸다 다시 (답변은 캐시라 다시 과금되지 않음)
                try:
                    res, hit = answer.chat(msgs, sample_idx=i)
                    resp = res.text or ""
                    g = grade_answer_accuracy(t["question"], t["answer"], t["key_facts"], resp, judge,
                                              mode="per_fact", judge_version="fact_judge_v3",
                                              alternatives=_alternatives(t))
                    break
                except Exception as e:          # noqa: BLE001
                    if attempt == 5:
                        raise
                    print(f"  재시도 {attempt + 1}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                    time.sleep(15 * (attempt + 1))
            fr = [x.satisfied for x in g.fact_results]
            row = {"arm": arm, "scenario": scn["scenario_id"], "turn": k, "ratio": r, "sample_idx": i,
                   "history_tokens": ht, "orig_history_tokens": n, "budget": B,
                   "accuracy": g.answer_accuracy,
                   "main_accuracy": main_accuracy(t, {"accuracy": g.answer_accuracy, "fact_results": fr}),
                   "fact_results": fr, "fact_sources": [(m or {}).get("source") for m in (t.get("fact_meta") or [])],
                   "not_found": is_not_found_answer(resp), "response": resp, "finish_reason": res.finish_reason, "cache_hit": hit,
                   "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
                   "judge_prompt_tokens": g.judge_prompt_tokens, "judge_completion_tokens": g.judge_completion_tokens,
                   "answer_model": res.model, "judge_model": judge.model, "judge_version": "fact_judge_v3"}
            with ROWS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(arm, scn["scenario_id"][:5], k, r, i, row["main_accuracy"], flush=True)
    if a.run:
        report()


if __name__ == "__main__":
    main()
