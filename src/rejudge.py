"""
기존 실험 결과 key_facts 재채점

results/runs/<run_id>/trials.jsonl 의 답변(response)을 그대로 두고 key_facts 판정만 다시 한다.
답변은 다시 생성하지 않는다. fact_judge_v1 (출력 예시가 index 0, 1 뿐이라 결과가 2개만 오던 프롬프트)로
채점한 결과를 현재 judge 로 다시 보고 싶을 때 쓴다.

    key_facts      trial 의 fact_results 에 든 fact 문장을 그대로 쓴다.
                   (--no-judge 로 돌려 fact_results 가 비었으면 평가셋에서 같은 qid 의 key_facts 를 읽는다)
    not_found      답변이 NOT FOUND 면 experiment.py 와 같이 answer_accuracy 를 0 으로 둔다.
    test split     test 문항 trial 은 재채점하지 않고 건너뛴다 (dev 로만 조정).

사용법

    python src/rejudge.py 20261010-153000
    python src/rejudge.py results/runs/20261010-153000/trials.jsonl --judge-mode per_fact
    python src/rejudge.py 20261010-153000 --judge-model qwen2.5:14b --out results/rejudge/x.jsonl

출력

    <out>                문항 x 압축기 단위 재채점 결과 (jsonl). 기존 정확도(old_*)와 새 정확도를 함께 기록
    <out>.summary.json   압축기별 / type 별 평균, 누락·재요청·폴백 횟수
    기본 <out> 은 results/runs/<run_id>/rejudge-<시각>-<mode>.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from experiment import FACT_JUDGE_MAX_TOKENS, TYPES, _mean, judge_counts, judge_fields
from grader import (
    FACT_JUDGE_PROMPT_HASH,
    FACT_JUDGE_PROMPT_VERSION,
    JUDGE_MODES,
    grade_answer_accuracy,
)
from llm import LLM


def resolve_trials(run: str) -> Path:
    """run_id 또는 trials.jsonl / run 디렉터리 경로를 trials.jsonl 경로로."""
    p = Path(run)
    if p.is_file():
        return p
    if p.is_dir() and (p / "trials.jsonl").is_file():
        return p / "trials.jsonl"
    p = CFG.results_dir / "runs" / run / "trials.jsonl"
    if p.is_file():
        return p
    sys.exit(f"trials.jsonl 을 찾을 수 없습니다: {run}")


def load_trials(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evalset_facts(qids: set[str]) -> dict[str, list[str]]:
    """fact_results 가 빈 trial 용. dev 문항의 key_facts 만 꺼낸다 (test 문항은 건너뜀)."""
    path = CFG.eval_dir / "qa_dataset.json"
    if not qids or not path.is_file():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    return {x["id"]: x.get("key_facts", []) for x in items
            if x["id"] in qids and x.get("split") != "test"}


def summarize(rows: list[dict]) -> dict:
    """압축기별 기존/새 정확도 평균, type 별 평균과 type 균등 평균, judge 보정 횟수."""
    out = {}
    for comp in dict.fromkeys(r["compressor"] for r in rows):
        rs = [r for r in rows if r["compressor"] == comp]
        by_type = {}
        for t in sorted({r["qtype"] for r in rs},
                        key=lambda t: (TYPES.index(t) if t in TYPES else len(TYPES), t)):
            ts = [r for r in rs if r["qtype"] == t]
            by_type[t] = {
                "n": len(ts),
                "old_answer_accuracy": _mean(r["old_answer_accuracy"] for r in ts),
                "answer_accuracy": _mean(r["answer_accuracy"] for r in ts),
                "fact_judge": judge_counts(ts),
            }
        out[comp] = {
            "n": len(rs),
            "old_answer_accuracy": _mean(r["old_answer_accuracy"] for r in rs),
            "answer_accuracy": _mean(r["answer_accuracy"] for r in rs),
            "old_answer_accuracy_type_avg": _mean(v["old_answer_accuracy"] for v in by_type.values()),
            "answer_accuracy_type_avg": _mean(v["answer_accuracy"] for v in by_type.values()),
            "fact_judge": judge_counts(rs),
            "by_type": by_type,
        }
    return out


def fmt(x) -> str:
    return "  -  " if x is None else f"{x:.3f}"


def print_summary(results: dict):
    print("\n" + "=" * 64)
    for comp, s in results.items():
        fj = s["fact_judge"]
        print(f"[{comp}] n={s['n']}  정확도 {fmt(s['old_answer_accuracy'])} -> {fmt(s['answer_accuracy'])}"
              f"  (type 평균 {fmt(s['old_answer_accuracy_type_avg'])} -> {fmt(s['answer_accuracy_type_avg'])})")
        print(f"    judge: 첫 응답 누락 문항 {fj['items_with_missing']} (index {fj['missing_indices']}개)  "
              f"재요청 {fj['retries']}  폴백 {fj['per_fact_fallbacks']}  호출 {fj['calls']}  모드 {fj['modes']}")
        for t, ts in s["by_type"].items():
            print(f"    {t:<10} n={ts['n']:<3} 정확도 {fmt(ts['old_answer_accuracy'])} -> {fmt(ts['answer_accuracy'])}"
                  f"  누락 {ts['fact_judge']['items_with_missing']}  재요청 {ts['fact_judge']['retries']}"
                  f"  폴백 {ts['fact_judge']['per_fact_fallbacks']}")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(description="기존 trials.jsonl 의 답변을 key_facts judge 로 재채점 (답변 재생성 없음)")
    ap.add_argument("run", help="run_id 또는 trials.jsonl 경로")
    ap.add_argument("--judge-model", default=CFG.judge_model, help=f"기본 {CFG.judge_model}")
    ap.add_argument("--judge-mode", default="batch", choices=JUDGE_MODES)
    ap.add_argument("--out", help="재채점 결과 jsonl 경로 (기본 results/runs/<run_id>/rejudge-<시각>-<mode>.jsonl)")
    args = ap.parse_args()

    trials_path = resolve_trials(args.run)
    trials = load_trials(trials_path)

    skipped_test = [t for t in trials if t.get("split") == "test"]
    trials = [t for t in trials if t.get("split") != "test"]
    if skipped_test:
        print(f"test split trial {len(skipped_test)}개는 건너뜁니다 (dev 만 재채점)")

    fallback_facts = evalset_facts({t["qid"] for t in trials if not t.get("fact_results")})

    out = Path(args.out) if args.out else (
        trials_path.parent / f"rejudge-{datetime.now():%Y%m%d-%H%M%S}-{args.judge_mode}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    judge = LLM(model=args.judge_model, max_tokens=FACT_JUDGE_MAX_TOKENS)
    print(f"입력: {trials_path}  ({len(trials)} trials)")
    print(f"judge: {args.judge_model}  {FACT_JUDGE_PROMPT_VERSION} ({FACT_JUDGE_PROMPT_HASH})  mode={args.judge_mode}")

    rows: list[dict] = []
    no_facts = 0
    with open(out, "w", encoding="utf-8") as f:
        for i, t in enumerate(trials, 1):
            facts = [x["fact"] for x in t.get("fact_results") or []] or fallback_facts.get(t["qid"], [])
            facts = [s for s in (str(x).strip() for x in facts) if s]
            if not facts:
                no_facts += 1
                continue

            g = grade_answer_accuracy(
                question=t["question"],
                reference_answer=t["answer"],
                key_facts=facts,
                candidate_answer=t["response"],
                judge_llm=judge,
                mode=args.judge_mode,
            )
            not_found = bool(t.get("not_found"))
            row = {
                "run_id": t.get("run_id"), "qid": t["qid"], "split": t.get("split"),
                "qtype": t.get("qtype"), "compressor": t["compressor"],
                "not_found": not_found,
                "old_answer_accuracy": t.get("answer_accuracy"),
                "old_satisfied_facts": t.get("satisfied_facts"),
                "old_judge_prompt_version": t.get("judge_prompt_version") or "fact_judge_v1",
                "answer_accuracy": 0.0 if not_found else g.answer_accuracy,
                "answer_accuracy_judged": g.answer_accuracy,
                "satisfied_facts": g.satisfied_count,
                "total_facts": g.total_count,
                "fact_results": [{"fact": r.fact, "satisfied": r.satisfied} for r in g.fact_results],
                "judge_model": args.judge_model,
                **judge_fields(g),
                "judge_prompt_tokens": g.judge_prompt_tokens,
                "judge_completion_tokens": g.judge_completion_tokens,
                "judge_raw": g.judge_raw,
            }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

            missing = row["judge_missing_before_fix"]
            print(f"[{i}/{len(trials)}] {t['qid']} {str(t.get('qtype')):<9} {t['compressor']:<8} "
                  f"{fmt(row['old_answer_accuracy'])} -> {fmt(row['answer_accuracy'])}  "
                  f"({g.satisfied_count}/{g.total_count})  {g.judge_mode}"
                  f"{f'  missing {missing}' if missing else ''}{'  NOT FOUND' if not_found else ''}",
                  flush=True)

    if no_facts:
        print(f"key_facts 가 없어 건너뛴 trial: {no_facts}개")

    results = summarize(rows)
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "source": trials_path.as_posix(),
        "judge": {"model": args.judge_model, "mode": args.judge_mode,
                  "prompt_version": FACT_JUDGE_PROMPT_VERSION, "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                  "max_tokens": FACT_JUDGE_MAX_TOKENS},
        "n_trials": len(rows), "skipped_test": len(skipped_test), "skipped_no_facts": no_facts,
        "results": results,
    }
    summary_path = out.with_name(out.name + ".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(results)
    print(f"\n저장: {out.as_posix()}\n      {summary_path.as_posix()}")


if __name__ == "__main__":
    main()
