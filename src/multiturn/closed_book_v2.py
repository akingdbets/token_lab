"""
multiturn-v2 closed-book 검사: 각 턴의 standalone_question 을 문서와 이전 대화 없이 답변 모델에 묻고 key_fact 를 맞히는지 본다.

    python src/multiturn/closed_book_v2.py data/evalsets/multiturn-v2/v2_01_auth_switch.json [...]

- 판정은 싱글턴 src/closed_book_check.py 의 check_item 을 그대로 쓴다 (CLOSED_BOOK_PROMPT, UNKNOWN·빈 답변 처리,
  key_facts per_fact 채점 = fact_judge_v2). 싱글턴 파일은 고치지 않는다.
- 답변 모델은 실험과 같은 설정: gpt-6-luna, reasoning_effort server_default, 출력 한도 4096, temperature 보내지 않음
  (replay.configure_llm).
- 결과를 시나리오 JSON 의 턴마다 "closed_book" 에 쓴다. correct = cb_accuracy == 1.0.
  맞힌 턴은 제외하지 않는다 (분석에서 따로 집계).
- 행별 원본 기록: results/closed_book_v2/<run_id>/closed_book.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CFG  # noqa: E402

ANSWER_MODEL, REASONING, MAX_TOKENS = "gpt-6-luna", "server_default", 4096


def make_llms():
    from llm import LLM
    from multiturn.replay import configure_llm
    answer = configure_llm(LLM(role="answer"), ANSWER_MODEL, REASONING, MAX_TOKENS, "server_default")
    return answer, LLM(role="judge")


def check_scenario(s: dict, answer, judge, run_id: str, out_rows: list) -> dict:
    from closed_book_check import check_item
    from cost import compute_cost  # noqa: F401  (비용은 행의 토큰으로 따로 계산)

    n_correct = 0
    for t in s["turns"]:
        item = {"id": f"{s['scenario_id']}#{t['turn']}", "split": "multiturn-v2", "type": t["type"],
                "question": t["standalone_question"], "answer": t["answer"],
                "key_entities": t.get("key_entities") or [], "key_facts": t["key_facts"]}
        row = check_item(item, answer, judge)
        acc = row["cb_accuracy"]
        t["closed_book"] = {"correct": acc == 1.0, "accuracy": acc, "unknown": row["unknown"], "empty": row["empty"],
                            "response": row["response"], "model": row["answer_model"], "settings": answer.sampling_info(),
                            "judge": judge.model, "judge_prompt": "fact_judge_v2", "run_id": run_id}
        n_correct += acc == 1.0
        out_rows.append({"scenario_id": s["scenario_id"], "turn": t["turn"], "turn_type": t["turn_type"], **row})
    return {"scenario_id": s["scenario_id"], "turns": len(s["turns"]), "closed_book_correct": n_correct,
            "closed_book_partial": sum(1 for t in s["turns"] if (t["closed_book"]["accuracy"] or 0) > 0
                                       and not t["closed_book"]["correct"]),
            "unknown": sum(1 for t in s["turns"] if t["closed_book"]["unknown"])}


def _usd(rows):
    from cost import cost_from_fields
    ans = sum(cost_from_fields(ANSWER_MODEL, r["prompt_tokens"], r["completion_tokens"]).usd or 0 for r in rows)
    jud = sum(cost_from_fields("deepseek-flash", r["judge_prompt_tokens"], r["judge_completion_tokens"]).usd or 0
              for r in rows)
    return round(ans, 6), round(jud, 6)


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 closed-book 검사")
    ap.add_argument("scenarios", nargs="+")
    a = ap.parse_args(argv)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = CFG.results_dir / "closed_book_v2" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    answer, judge = make_llms()
    rows, summary = [], []
    for path in a.scenarios:
        s = json.loads(Path(path).read_text(encoding="utf-8"))
        summary.append(check_scenario(s, answer, judge, run_id, rows))
        Path(path).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out_dir / "closed_book.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ans_usd, judge_usd = _usd(rows)
    out = {"run_id": run_id, "scenarios": summary, "answer_usd_nocache": ans_usd, "judge_usd_nocache": judge_usd,
           "settings": answer.sampling_info()}
    (out_dir / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
