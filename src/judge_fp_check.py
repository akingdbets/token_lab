"""
채점기 FP 확인: 일부러 틀리게 만든 답을 key_facts judge 로 채점해 틀린 fact 에 O 를 준 비율을 본다

세트: docs/results/judge_fp_set_v1.csv (fact 한 줄당 한 행)
    qid, type, method, how, fact_idx, key_fact, wrong_answer, expected, human, note
    - method/how: 어떻게 틀리게 했는지 (value_swap, step_drop, part_swap, near_miss_name, contradiction ...)
    - expected: 그 fact 의 기대 판정 (틀리게 만든 fact 는 X, 그대로 둔 fact 는 O)
    - human: 사람이 확인한 판정 (O/X). 채워져 있으면 expected 대신 쓴다
문항의 question·answer(정답)·key_facts 는 평가셋(EVAL_DIR)에서 읽는다. judge 는 실험과 같은 JUDGE_* / per_fact.

    EVAL_DIR=data/evalsets/claude-v1 python src/judge_fp_check.py docs/results/judge_fp_set_v1.csv

결과: results/judge_fp/<세트 이름>.jsonl (fact 별 판정) 과 요약 출력
    FP 율 = 기대 X 인 fact 중 judge 가 O 를 준 비율
    FN 율 = 기대 O 인 fact 중 judge 가 X 를 준 비율
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from experiment import FACT_JUDGE_MAX_TOKENS, load_items
from grader import FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION, grade_answer_accuracy
from llm import LLM


def read_set(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def label(row: dict) -> str:
    """사람 확인값이 있으면 그것, 없으면 expected."""
    h = (row.get("human") or "").strip().upper()
    return h if h in ("O", "X") else row["expected"].strip().upper()


def rates(rows: list[dict]) -> dict:
    exp_x = [r for r in rows if r["label"] == "X" and r["judge"] in ("O", "X")]
    exp_o = [r for r in rows if r["label"] == "O" and r["judge"] in ("O", "X")]
    fp = sum(r["judge"] == "O" for r in exp_x)
    fn = sum(r["judge"] == "X" for r in exp_o)
    return {"n_expected_x": len(exp_x), "fp": fp, "fp_rate": round(fp / len(exp_x), 4) if exp_x else None,
            "n_expected_o": len(exp_o), "fn": fn, "fn_rate": round(fn / len(exp_o), 4) if exp_o else None,
            "unread": sum(r["judge"] == "?" for r in rows)}


def main():
    ap = argparse.ArgumentParser(description="틀린 답 세트로 key_facts judge 의 FP 확인")
    ap.add_argument("set", help="judge_fp_set csv")
    ap.add_argument("--out", help="결과 jsonl (기본 results/judge_fp/<세트 이름>.jsonl)")
    args = ap.parse_args()

    set_path = Path(args.set)
    rows = read_set(set_path)
    items = {it["id"]: it for it in load_items("all", None, None)}
    by_qid: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_qid[r["qid"]].append(r)

    judge = LLM(role="judge", max_tokens=FACT_JUDGE_MAX_TOKENS)
    out = Path(args.out) if args.out else CFG.results_dir / "judge_fp" / f"{set_path.stem}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for qid, rs in by_qid.items():
        it = items[qid]
        answers = {r["wrong_answer"] for r in rs}
        if len(answers) != 1 or [r["key_fact"] for r in rs] != it["key_facts"]:
            sys.exit(f"{qid}: 틀린 답이 한 문항에 하나가 아니거나 key_fact 가 평가셋과 다릅니다")
        g = grade_answer_accuracy(it["question"], it["answer"], it["key_facts"], answers.pop(), judge, mode="per_fact")
        for r, fr in zip(rs, g.fact_results):
            results.append({**{k: r[k] for k in ("qid", "type", "method", "how", "fact_idx", "key_fact", "expected")},
                            "label": label(r),
                            "judge": "?" if fr.satisfied is None else "O" if fr.satisfied else "X"})
        print(f"{qid} {rs[0]['method']:<22} 기대 {''.join(label(r) for r in rs)}  judge "
              f"{''.join(x['judge'] for x in results[-len(rs):])}", flush=True)

    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {
        "set": set_path.as_posix(), "judge": judge.sampling_info(),
        "fact_judge": {"prompt_version": FACT_JUDGE_PROMPT_VERSION, "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                       "mode": "per_fact"},
        "all": rates(results),
        "by_method": {m: rates([r for r in results if r["method"] == m])
                      for m in dict.fromkeys(r["method"] for r in results)},
    }
    out.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    a = summary["all"]
    print(f"\nFP {a['fp']}/{a['n_expected_x']} ({a['fp_rate']})  FN {a['fn']}/{a['n_expected_o']} ({a['fn_rate']})  "
          f"못 읽음 {a['unread']}  ->  {out}")


if __name__ == "__main__":
    main()
