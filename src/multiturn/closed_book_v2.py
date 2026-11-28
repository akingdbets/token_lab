"""
multiturn-v2 closed-book 검사 두 종류. 각 턴의 standalone_question 을 문서와 이전 대화 없이 답변 모델에 묻는다.

    python src/multiturn/closed_book_v2.py data/evalsets/multiturn-v2/v2_01_auth_switch.json [...]

knowledge  (턴 필드 closed_book_knowledge)
    싱글턴 src/closed_book_check.py 의 CLOSED_BOOK_PROMPT 그대로 ("모르면 UNKNOWN"). 모델이 사전 지식으로 맞히는지.
    질문·UNKNOWN·빈 답변 처리는 check_item 을 그대로 쓰고 (judge 없이 부른다), 채점만 아래 judge 로 한다.
grounded   (턴 필드 closed_book_grounded)
    실험과 같은 답변 지시문 mt_answer_v2 (system + user_no_docs, NOT FOUND 규칙 포함) 로 문서·기록 없이 묻는다.
    NOT FOUND 대신 정답을 내면 압축 결과를 오염시킨다 (압축으로 정보를 잃어도 맞힐 수 있으므로).
    NOT FOUND·빈 답변은 grade_answer_accuracy 가 judge 없이 0 으로 처리한다.

- 채점: deepseek-flash, fact_judge_v3, per_fact, fact_meta 의 accept_alternatives 를 넘긴다. correct 는 setup 태그를 뺀 key_fact 기준
  (대안이 없는 fact 는 v2 와 같은 프롬프트). correct = accuracy_main == 1.0 (setup 제외), accuracy 는 전체 fact 기준.
- 답변 모델은 실험과 같은 설정: gpt-6-luna, reasoning_effort server_default, 출력 한도 4096, temperature 보내지 않음
  (replay.configure_llm).
- 결과를 시나리오 JSON 의 턴마다 쓴다. 맞힌 턴은 제외하지 않는다 (분석에서 따로 집계).
  예전 필드 closed_book 은 지운다 (closed_book_knowledge 로 바뀜).
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
ANSWER_PROMPT_VERSION = "v2"         # mt_answer_v2 (실험과 같은 지시문)
JUDGE_VERSION = "fact_judge_v3"
KINDS = ("knowledge", "grounded")


def make_llms():
    from llm import LLM
    from multiturn.replay import configure_llm
    answer = configure_llm(LLM(role="answer"), ANSWER_MODEL, REASONING, MAX_TOKENS, "server_default")
    return answer, LLM(role="judge")


def grounded_messages(t: dict, prompt) -> list[dict]:
    """실험의 첫 턴(문서 없는 턴)과 같은 모양: system + user_no_docs."""
    return [{"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user_text(t["standalone_question"], t.get("type"), None)}]


def _alternatives(t: dict) -> list[list[str]]:
    meta = t.get("fact_meta") or [{}] * len(t["key_facts"])
    return [list((m or {}).get("accept_alternatives") or []) for m in meta]


def _grade(t: dict, response: str, judge) -> dict:
    from grader import grade_answer_accuracy
    g = grade_answer_accuracy(t["standalone_question"], t["answer"], t["key_facts"], response, judge,
                              mode="per_fact", judge_version=JUDGE_VERSION, alternatives=_alternatives(t))
    # judge 를 부르지 않은 경우(NOT FOUND·빈 답변) 결과 객체의 기본 버전 표시는 v2 라서 v3 로 적는다
    skipped = g.judge_skipped is not None
    return {"accuracy": g.answer_accuracy, "fact_results": [r.satisfied for r in g.fact_results],
            "judge_skipped": g.judge_skipped,
            "judge_prompt_version": JUDGE_VERSION if skipped else g.judge_prompt_version,
            "judge_prompt_hash": None if skipped else g.judge_prompt_hash, "judge_prompt_tokens": g.judge_prompt_tokens,
            "judge_completion_tokens": g.judge_completion_tokens}


def check_knowledge(t: dict, sid: str, answer, judge) -> dict:
    from closed_book_check import check_item
    item = {"id": f"{sid}#{t['turn']}", "split": "multiturn-v2", "type": t["type"],
            "question": t["standalone_question"], "answer": t["answer"],
            "key_entities": t.get("key_entities") or [], "key_facts": t["key_facts"]}
    row = check_item(item, answer, None)          # 질문·UNKNOWN·빈 답변 판정만 (채점은 v3 로 따로)
    out = {"response": row["response"], "unknown": row["unknown"], "empty": row["empty"],
           "prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"],
           "finish_reason": row["finish_reason"], "model": row["answer_model"]}
    if row["unknown"]:
        out.update(accuracy=0.0, fact_results=[False] * len(t["key_facts"]), judge_skipped="unknown",
                   judge_prompt_tokens=0, judge_completion_tokens=0)
    elif row["empty"]:      # 빈 답변은 판정에서 뺀다 (싱글턴과 같음)
        out.update(accuracy=None, fact_results=[], judge_skipped="empty", judge_prompt_tokens=0,
                   judge_completion_tokens=0)
    else:
        out.update(_grade(t, row["response"], judge))
    return out


def check_grounded(t: dict, answer, judge, prompt) -> dict:
    from grader import is_not_found_answer
    res = answer.chat(grounded_messages(t, prompt))
    resp = (res.text or "").strip()
    out = {"response": resp, "not_found": is_not_found_answer(resp), "empty": not resp,
           "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
           "finish_reason": res.finish_reason, "model": res.model}
    out.update(_grade(t, resp, judge))
    return out


def main_accuracy(t: dict, r: dict) -> float | None:
    """setup 태그를 뺀 key_fact 의 정확도 (주 정확도와 같은 기준, 2026-11-28 검수 결정). correct = 이 값이 1.0."""
    if r["accuracy"] is None:
        return None
    keep = [i for i, m in enumerate(t.get("fact_meta") or [{}] * len(t["key_facts"]))
            if "setup" not in ((m or {}).get("tags") or [])]
    fr = r["fact_results"]
    if not keep:
        return r["accuracy"]
    if len(fr) < len(t["key_facts"]):        # judge 를 안 부른 경우 (UNKNOWN 등): 전체 정확도 그대로 (0)
        return r["accuracy"]
    return sum(bool(fr[i]) for i in keep) / len(keep)


def check_scenario(s: dict, answer, judge, run_id: str, out_rows: list, prompt) -> dict:
    summary = {"scenario_id": s["scenario_id"], "turns": len(s["turns"])}
    for t in s["turns"]:
        t.pop("closed_book", None)
        for kind in KINDS:
            r = (check_knowledge(t, s["scenario_id"], answer, judge) if kind == "knowledge"
                 else check_grounded(t, answer, judge, prompt))
            acc, main = r["accuracy"], main_accuracy(t, r)
            t[f"closed_book_{kind}"] = {
                "correct": main == 1.0, "accuracy_main": main, "accuracy": acc, "response": r["response"],
                "fact_results": r["fact_results"], "judge_skipped": r["judge_skipped"],
                **({"unknown": r["unknown"]} if kind == "knowledge" else {"not_found": r["not_found"],
                                                                         "answer_prompt": ["mt_answer_v2", prompt.sha256]}),
                "empty": r["empty"], "model": r["model"], "settings": answer.sampling_info(), "judge": judge.model,
                "judge_prompt": [r.get("judge_prompt_version") or JUDGE_VERSION, r.get("judge_prompt_hash")],
                "run_id": run_id}
            out_rows.append({"scenario_id": s["scenario_id"], "turn": t["turn"], "turn_type": t["turn_type"],
                             "kind": kind, **r})
    for kind in KINDS:
        summary[f"{kind}_correct"] = sum(1 for t in s["turns"] if t[f"closed_book_{kind}"]["correct"])
    summary["grounded_not_found"] = sum(1 for t in s["turns"] if t["closed_book_grounded"]["not_found"])
    summary["knowledge_unknown"] = sum(1 for t in s["turns"] if t["closed_book_knowledge"]["unknown"])
    return summary


def _usd(rows):
    from cost import cost_from_fields
    ans = sum(cost_from_fields(ANSWER_MODEL, r["prompt_tokens"], r["completion_tokens"]).usd or 0 for r in rows)
    jud = sum(cost_from_fields("deepseek-flash", r.get("judge_prompt_tokens") or 0,
                               r.get("judge_completion_tokens") or 0).usd or 0 for r in rows)
    return round(ans, 6), round(jud, 6)


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 closed-book 검사 (knowledge, grounded)")
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--workers", type=int, default=1, help="시나리오 단위 동시 실행 수 (시나리오마다 LLM 객체를 따로 만든다)")
    a = ap.parse_args(argv)
    from concurrent.futures import ThreadPoolExecutor

    from multiturn.prompt import load_mt_prompt
    prompt = load_mt_prompt(ANSWER_PROMPT_VERSION)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = CFG.results_dir / "closed_book_v2" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    answer, _ = make_llms()

    def one(path):
        ans, jud = make_llms()
        s = json.loads(Path(path).read_text(encoding="utf-8"))
        rows_one = []
        summ = check_scenario(s, ans, jud, run_id, rows_one, prompt)
        Path(path).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{s['scenario_id']}: knowledge {summ['knowledge_correct']}, grounded {summ['grounded_correct']}", flush=True)
        return summ, rows_one

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        results = list(ex.map(one, a.scenarios))
    summary = [r[0] for r in results]
    rows = [x for r in results for x in r[1]]
    with open(out_dir / "closed_book.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ans_usd, judge_usd = _usd(rows)
    out = {"run_id": run_id, "scenarios": summary, "answer_usd_nocache": ans_usd, "judge_usd_nocache": judge_usd,
           "settings": answer.sampling_info(), "answer_prompt": ["mt_answer_v2", prompt.sha256],
           "judge_version": JUDGE_VERSION}
    (out_dir / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
