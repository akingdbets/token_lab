"""reasoning probe: 같은 압축 문맥에서 답변 설정(생각 토큰·temperature)만 바꿔 다시 답하게 한다.

test_v1 run 에 저장된 contexts 를 그대로 쓴다 (다시 압축하지 않음). 채점은 test_v1 과 같다
(deepseek-flash, fact_judge_v2, per_fact). O/X judge 는 부르지 않는다.

대상 trial (select_targets, 결정적):
  - llmlingua2_r50·llmlingua2_r30·rule>llmlingua2 에서 answer_accuracy < 0.5 인 trial 전부
  - 같은 세 압축기의 완전 정답(answer_accuracy == 1) trial 중 random.Random(42) 로 30개
  - 위 trial 에 나오는 문항의 none trial

설정:
  current  test_v1 과 같다: reasoning_effort none, temperature 0, seed 42, 출력 상한 512
  default  temperature·reasoning_effort 를 보내지 않는다 (서버 기본값). seed 42, 출력 상한 4096
  temp_default  reasoning_effort none 은 보내고 temperature 는 보내지 않는다. seed 42, 출력 상한 512
                (--repeat N 으로 반복, results/reasoning_probe/temp_default_r<N>/)
  서버가 보낸 인자를 거부하면 llm.py 는 빼고 다시 보내는데, 그러면 설정이 바뀌므로 바로 멈춘다.

    EVAL_DIR=data/evalsets/claude-v1 python src/reasoning_probe.py targets results/runs/<test_run>
    EVAL_DIR=data/evalsets/claude-v1 python src/reasoning_probe.py run results/runs/<test_run> --setting current
    EVAL_DIR=data/evalsets/claude-v1 python src/reasoning_probe.py run results/runs/<test_run> --setting default

결과는 results/reasoning_probe/<setting>/trials.jsonl (끊기면 같은 명령으로 이어서 실행).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from config import CFG
from experiment import (ANSWER_MAX_TOKENS, FACT_JUDGE_MAX_TOKENS, git_head, is_not_found, judge_fields,
                        load_answer_prompt, load_items)
from grader import FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION, grade_answer_accuracy
from llm import LLM, count_message_tokens

COMPRESSORS = ("llmlingua2_r50", "llmlingua2_r30", "rule>llmlingua2")
N_RIGHT = 30
SEED = 42
SETTINGS = {
    "current": {"max_tokens": ANSWER_MAX_TOKENS, "omit_temperature": False, "omit_reasoning": False},
    "default": {"max_tokens": 4096, "omit_temperature": True, "omit_reasoning": True},
    # current 와 temperature 만 다르다 (temperature 효과 = temp_default − current)
    "temp_default": {"max_tokens": ANSWER_MAX_TOKENS, "omit_temperature": True, "omit_reasoning": False},
}
OUT_ROOT = CFG.root / "results" / "reasoning_probe"


def load_trials(run_dir: Path) -> list[dict]:
    return [json.loads(l) for l in open(run_dir / "trials.jsonl", encoding="utf-8") if l.strip()]


def select_targets(trials: list[dict]) -> list[dict]:
    """대상 trial (원래 trial 기록에 group: wrong / right / none 을 붙여 돌려준다)."""
    acc = lambda t: t["answer_accuracy"]  # noqa: E731
    key = lambda t: (t["qid"], t["compressor"])  # noqa: E731
    wrong = sorted((t for t in trials if t["compressor"] in COMPRESSORS and acc(t) is not None and acc(t) < 0.5),
                   key=key)
    pool = sorted((t for t in trials if t["compressor"] in COMPRESSORS and acc(t) == 1.0), key=key)
    right = random.Random(SEED).sample(pool, N_RIGHT)
    qids = sorted({t["qid"] for t in wrong + right})
    none = {t["qid"]: t for t in trials if t["compressor"] == "none"}
    return ([{**t, "group": "wrong"} for t in wrong] + [{**t, "group": "right"} for t in sorted(right, key=key)]
            + [{**none[q], "group": "none"} for q in qids])


def build_messages(prompt, item: dict, t: dict, run_dir: Path) -> list[dict]:
    """test_v1 trial 과 같은 메시지: 저장된 압축 문맥 + (압축됐다면) 압축된 지시문·질문."""
    ctx = (run_dir / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md").read_text(encoding="utf-8")
    parts = prompt.parts(ctx, item["question"], item.get("type"))
    system = t.get("system_compressed") or parts.system
    question = t.get("question_compressed") or parts.question
    return prompt.messages(type(parts)(system=system, context=ctx, question=question))


def make_llm(setting: str) -> LLM:
    s = SETTINGS[setting]
    llm = LLM(max_tokens=s["max_tokens"])
    if s["omit_temperature"]:
        llm.unsupported.add("temperature")   # 보내지 않음
    if s["omit_reasoning"]:
        llm.reasoning_effort = ""            # 보내지 않음
    return llm


def grade_with_wait(item: dict, facts: list[str], answer: str, judge: LLM):
    """judge 서버가 바쁘면 기다렸다 채점만 다시 한다. 429·503 과, 과부하 때 200 으로 오는 빈 응답
    (choices 가 null 이라 TypeError·KeyError)을 기다린다. 답변은 다시 부르지 않는다."""
    for wait in (*CFG.network_retry_waits, None):
        try:
            return grade_answer_accuracy(question=item["question"], reference_answer=item["answer"],
                                         key_facts=facts, candidate_answer=answer, judge_llm=judge,
                                         mode="per_fact")
        except (requests.HTTPError, TypeError, KeyError) as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if wait is None or (isinstance(e, requests.HTTPError) and code not in (429, 503)):
                raise
            print(f"  [judge 대기] {code or type(e).__name__} ({wait}초 후 다시 채점)", flush=True)
            time.sleep(wait)


def cmd_targets(args) -> None:
    run_dir = Path(args.run)
    items = {it["id"]: it for it in load_items("test", None, None)}
    prompt = load_answer_prompt("v1")
    targets = select_targets(load_trials(run_dir))
    groups = {g: sum(t["group"] == g for t in targets) for g in ("wrong", "right", "none")}
    bad = [(t["qid"], t["compressor"]) for t in targets
           if count_message_tokens(build_messages(prompt, items[t["qid"]], t, run_dir)) != t["input_tokens"]]
    print("대상", len(targets), groups, "입력 토큰이 test_v1 과 다른 trial", bad)


def cmd_run(args) -> None:
    run_dir = Path(args.run)
    items = {it["id"]: it for it in load_items("test", None, None)}
    prompt = load_answer_prompt("v1")
    targets = select_targets(load_trials(run_dir))
    out_dir = OUT_ROOT / (args.setting if args.repeat is None else f"{args.setting}_r{args.repeat}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "trials.jsonl"
    done = set()
    if path.exists():
        done = {(r["qid"], r["compressor"]) for r in map(json.loads, open(path, encoding="utf-8")) if r}
    llm = make_llm(args.setting)
    judge = LLM(role="judge", max_tokens=FACT_JUDGE_MAX_TOKENS)
    print(f"설정 {args.setting}: {llm.sampling_info()}  대상 {len(targets)}, 이미 {len(done)}", flush=True)
    served = {}
    apath = out_dir / "answers.jsonl"
    answers = ({(r["qid"], r["compressor"]): r for r in map(json.loads, open(apath, encoding="utf-8"))}
               if apath.exists() else {})
    with open(path, "a", encoding="utf-8") as f, open(apath, "a", encoding="utf-8") as af:
        for i, t in enumerate(targets, 1):
            if (t["qid"], t["compressor"]) in done:
                continue
            item = items[t["qid"]]
            messages = build_messages(prompt, item, t, run_dir)
            a = answers.get((t["qid"], t["compressor"]))
            if a is None:
                res = llm.chat(messages)            # 스트리밍 없이: usage 세부(생각 토큰)를 받는다
                # 서버가 temperature·reasoning_effort 를 거부해 llm.py 가 빼고 보냈다면 다른 설정이 된 것이다
                dropped = {"temperature", "reasoning_effort"} & llm.unsupported - {
                    k for k, omit in (("temperature", SETTINGS[args.setting]["omit_temperature"]),
                                      ("reasoning_effort", SETTINGS[args.setting]["omit_reasoning"])) if omit}
                if dropped:
                    sys.exit(f"서버가 {sorted(dropped)} 를 거부했습니다. 설정 {args.setting} 을 그대로 보낼 수 없어 멈춥니다 "
                             f"(이 답변은 기록하지 않음)")
                usage = res.raw.get("usage") or {}
                a = {"qid": t["qid"], "compressor": t["compressor"], "text": res.text,
                     "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
                     "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                     "finish_reason": res.finish_reason, "latency_sec": round(res.latency, 3),
                     # 응답에 나오는 생성 조건 (chat completions 는 보통 주지 않는다)
                     "served": {k: res.raw[k] for k in ("temperature", "reasoning_effort", "service_tier",
                                                        "system_fingerprint") if k in res.raw} or None}
                # 채점 전에 답변부터 남긴다: judge 가 실패해 다시 실행해도 답변을 다시 부르지 않는다
                af.write(json.dumps(a, ensure_ascii=False) + "\n")
                af.flush()
            served = a["served"] or served
            text = a["text"]
            not_found = is_not_found(text)
            facts = item.get("key_facts") or []
            fg = None
            if facts and text.strip() and not not_found:
                fg = grade_with_wait(item, facts, text, judge)
            acc = 0.0 if facts and (not_found or not text.strip()) else (fg.answer_accuracy if fg else None)
            rec = {
                "setting": args.setting, "repeat": args.repeat, "qid": t["qid"], "qtype": item["type"], "compressor": t["compressor"],
                "group": t["group"], "input_tokens": count_message_tokens(messages),
                "prompt_tokens": a["prompt_tokens"], "completion_tokens": a["completion_tokens"],
                "reasoning_tokens": a["reasoning_tokens"],
                "finish_reason": a["finish_reason"], "empty": not text.strip(),
                "response": text.strip(), "not_found": not_found, "answer_accuracy": acc,
                "satisfied_facts": fg.satisfied_count if fg else None, "total_facts": len(facts),
                "latency_sec": a["latency_sec"], "served": a["served"],
                "v1_answer_accuracy": t["answer_accuracy"], "v1_not_found": t["not_found"],
                "v1_completion_tokens": t["completion_tokens"],
                **judge_fields(fg),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(targets)}] {t['qid']} {t['compressor']:<16} {t['group']:<5} "
                  f"acc {t['answer_accuracy']} -> {acc}  out {a['completion_tokens']}"
                  f" (생각 {a['reasoning_tokens']})  {a['finish_reason']}{'  NOT FOUND' if not_found else ''}",
                  flush=True)
    summary = {"setting": args.setting, "repeat": args.repeat, "time": datetime.now().isoformat(timespec="seconds"),
               "git_head": git_head(), "source_run": run_dir.name, "sampling": llm.sampling_info(),
               "served": served or None, "judge": judge.sampling_info(),
               "fact_judge": {"prompt_version": FACT_JUDGE_PROMPT_VERSION, "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                              "mode": "per_fact", "max_tokens": FACT_JUDGE_MAX_TOKENS},
               "answer_prompt": {"version": prompt.version, "sha256": prompt.sha256}}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("targets", help="대상 trial 을 고르고 메시지가 test_v1 과 같은지 확인 (API 호출 없음)")
    a.add_argument("run")
    a = sub.add_parser("run", help="한 설정으로 답변·채점 (과금)")
    a.add_argument("run")
    a.add_argument("--setting", choices=sorted(SETTINGS), required=True)
    a.add_argument("--repeat", type=int, help="반복 번호 (결과 폴더 <setting>_r<N>)")
    args = ap.parse_args()
    {"targets": cmd_targets, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
