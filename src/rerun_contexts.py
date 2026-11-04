"""저장된 압축 문맥으로 답변만 다시 받는 run (다시 압축하지 않음).

원래 run 의 trial 기록을 복사하고 답변·채점 필드만 새 답변으로 바꾼다. 그래서 새 run 폴더에도
stats.py, redundancy.py, memory_suspect.py 를 그대로 쓸 수 있다 (contexts/ 도 복사한다).

답변 설정은 서버 기본값이다: temperature·reasoning_effort 를 요청에 넣지 않는다. seed 는 보낸다.
채점은 원래 run 과 같다 (key_facts judge, per_fact). O/X judge 는 부르지 않는다
(correct 는 key_facts 완전 충족 여부, grade_method "fact_full").

    EVAL_DIR=data/evalsets/claude-v1 python src/rerun_contexts.py results/runs/<src_run> --model gpt-6-luna \\
        --compressors "none,rule,llmlingua2_r50,llmlingua2_r30,rule>llmlingua2"
    ... --resume <RUN_ID>      # 끊긴 run 에 이어서 (답변은 answers.jsonl 에 먼저 남겨 다시 부르지 않는다)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import requests

from config import CFG
from experiment import (FACT_JUDGE_MAX_TOKENS, TrialRecord, git_head, is_not_found, judge_fields, load_answer_prompt,
                        load_items, memory_suspect, print_summary, summarize)
from grader import FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION, grade_answer_accuracy
from llm import LLM, count_message_tokens

ANSWER_MAX_TOKENS = 4096   # 생각 토큰 포함
RETRY_CODES = (429, 500, 502, 503, 504)   # 서버가 받지 않은 요청이라 과금되지 않는다


def with_wait(fn, what: str):
    """호출 제한·서버 과부하(429·5xx, 과부하 때 오는 빈 200 응답)면 기다렸다 다시 부른다."""
    for wait in (*CFG.network_retry_waits, None):
        try:
            return fn()
        except (requests.HTTPError, TypeError, KeyError) as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if wait is None or (isinstance(e, requests.HTTPError) and code not in RETRY_CODES):
                raise
            print(f"  [{what} 대기] {code or type(e).__name__} ({wait}초 후 다시)", flush=True)
            time.sleep(wait)


def build_messages(prompt, item: dict, t: dict, src: Path) -> list[dict]:
    """원래 trial 과 같은 메시지: 저장된 압축 문맥 + (압축됐다면) 압축된 지시문·질문."""
    ctx = (src / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md").read_text(encoding="utf-8")
    parts = prompt.parts(ctx, item["question"], item.get("type"))
    system = t.get("system_compressed") or parts.system
    question = t.get("question_compressed") or parts.question
    return prompt.messages(type(parts)(system=system, context=ctx, question=question))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src_run")
    ap.add_argument("--model", required=True, help="답변 모델 ID")
    ap.add_argument("--compressors", required=True)
    ap.add_argument("--resume", metavar="RUN_ID")
    args = ap.parse_args()
    src = Path(args.src_run)
    names = [n.strip() for n in args.compressors.split(",") if n.strip()]
    items = {it["id"]: it for it in load_items("test", None, None)}
    prompt = load_answer_prompt("v1")
    src_trials = [json.loads(l) for l in open(src / "trials.jsonl", encoding="utf-8") if l.strip()]
    targets = [t for t in src_trials if t["compressor"] in names and t["qid"] in items]

    run_id = args.resume or datetime.now().strftime("%Y%m%d-%H%M%S")
    out = CFG.root / "results" / "runs" / run_id
    (out / "contexts").mkdir(parents=True, exist_ok=True)
    for t in targets:
        f = f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
        if not (out / "contexts" / f).exists():
            shutil.copy2(src / "contexts" / f, out / "contexts" / f)

    llm = LLM(model=args.model, max_tokens=ANSWER_MAX_TOKENS)
    llm.unsupported.add("temperature")   # 보내지 않음 (서버 기본값)
    llm.reasoning_effort = ""            # 보내지 않음 (서버 기본값)
    judge = LLM(role="judge", max_tokens=FACT_JUDGE_MAX_TOKENS)

    tpath, apath = out / "trials.jsonl", out / "answers.jsonl"
    done = ({(r["qid"], r["compressor"]) for r in map(json.loads, open(tpath, encoding="utf-8"))}
            if tpath.exists() else set())
    answers = ({(r["qid"], r["compressor"]): r for r in map(json.loads, open(apath, encoding="utf-8"))}
               if apath.exists() else {})
    print(f"run {run_id}  모델 {args.model}  {llm.sampling_info()}  대상 {len(targets)}, 이미 {len(done)}", flush=True)
    served_model, served = None, None
    with open(tpath, "a", encoding="utf-8") as tf, open(apath, "a", encoding="utf-8") as af:
        for i, t in enumerate(targets, 1):
            key = (t["qid"], t["compressor"])
            if key in done:
                continue
            item = items[t["qid"]]
            messages = build_messages(prompt, item, t, src)
            a = answers.get(key)
            if a is None:
                res = with_wait(lambda: llm.chat(messages), "답변")
                if "reasoning_effort" in llm.unsupported:
                    sys.exit("서버가 reasoning_effort 없는 요청을 거부했습니다 (예상 밖). 멈춥니다")
                usage = res.raw.get("usage") or {}
                a = {"qid": t["qid"], "compressor": t["compressor"], "text": res.text, "model": res.model,
                     "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
                     "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                     "finish_reason": res.finish_reason, "latency_sec": round(res.latency, 3),
                     "usage_source": res.usage_source,
                     "served": {k: res.raw[k] for k in ("temperature", "reasoning_effort", "service_tier",
                                                        "system_fingerprint") if k in res.raw} or None}
                af.write(json.dumps(a, ensure_ascii=False) + "\n")
                af.flush()
            served_model, served = a["model"] or served_model, a["served"] or served
            text = a["text"]
            not_found = is_not_found(text)
            facts = item.get("key_facts") or []
            fg = None
            if facts and text.strip() and not not_found:
                fg = with_wait(lambda: grade_answer_accuracy(
                    question=item["question"], reference_answer=item["answer"], key_facts=facts,
                    candidate_answer=text, judge_llm=judge, mode="per_fact"), "judge")
            judged = fg.answer_accuracy if fg else None
            acc = 0.0 if facts and (not_found or not text.strip()) else judged
            rec = {**t, "run_id": run_id, "response": text.strip(), "prompt_tokens": a["prompt_tokens"],
                   "completion_tokens": a["completion_tokens"], "not_found": not_found, "ttft_sec": None,
                   "latency_sec": a["latency_sec"], "ctx_overflow": False,
                   "correct": acc == 1.0, "grade_method": "fact_full", "match": None, "judge": None, "judge_raw": None,
                   "ox_judge_error": None, "ox_judge_prompt_tokens": 0, "ox_judge_completion_tokens": 0,
                   "answer_accuracy": acc, "answer_accuracy_judged": judged,
                   "satisfied_facts": fg.satisfied_count if fg else None,
                   "total_facts": fg.total_count if fg else (len(facts) if facts else None),
                   "fact_results": [asdict(r) for r in fg.fact_results] if fg else [],
                   **{k: None for k in ("judge_prompt_version", "judge_prompt_hash", "judge_mode")},
                   "judge_retries": 0, "judge_missing_before_fix": [], "judge_calls": 0, "judge_skipped": [],
                   "judge_failed": [], "judge_errors": [], "judge_prompt_tokens": 0, "judge_completion_tokens": 0,
                   **judge_fields(fg),
                   "judge_usage_source": "api" if fg else None,
                   "answer_model": a["model"], "answer_usage_source": a["usage_source"],
                   "answer_finish_reason": a["finish_reason"],
                   "memory_suspect": memory_suspect(t.get("answer_core_in_context"), acc),
                   "memory_suspect_strict": memory_suspect(t.get("answer_core_in_context_strict"), acc),
                   "reasoning_tokens": a["reasoning_tokens"], "empty": not text.strip(),
                   "source_run": src.name}
            tf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tf.flush()
            print(f"[{i}/{len(targets)}] {t['qid']} {t['compressor']:<16} acc {t['answer_accuracy']} -> {acc}  "
                  f"out {a['completion_tokens']} (생각 {a['reasoning_tokens']})  {a['finish_reason']}"
                  f"{'  NOT FOUND' if not_found else ''}", flush=True)

    fields = set(TrialRecord.__dataclass_fields__)
    rows = [json.loads(l) for l in open(tpath, encoding="utf-8") if l.strip()]
    records = [TrialRecord(**{k: v for k, v in r.items() if k in fields}) for r in rows]
    src_summary = json.loads((src / "summary.json").read_text(encoding="utf-8"))
    summary = {
        "run_id": run_id, "time": datetime.now().isoformat(timespec="seconds"), "git_head": git_head(),
        "source_run": src.name, "reuse_contexts": True,
        "config": {**src_summary["config"], "llm": f"model={args.model} (기본 설정: temperature·reasoning_effort 안 보냄)",
                   "answer_model_served": served_model, "served": served,
                   "sampling": {"answer": llm.sampling_info(), "fact_judge": judge.sampling_info()},
                   "answer_max_tokens": ANSWER_MAX_TOKENS, "ox_judge_max_tokens": None,
                   "fact_judge": {"prompt_version": FACT_JUDGE_PROMPT_VERSION, "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                                  "mode": "per_fact", "max_tokens": FACT_JUDGE_MAX_TOKENS}},
        "counts": {"trials": len(rows), "length": sum(r["answer_finish_reason"] == "length" for r in rows),
                   "empty": sum(r["empty"] for r in rows),
                   "judge_failed": sum(bool(r["judge_failed"]) for r in rows),
                   "reasoning_tokens": sum(r["reasoning_tokens"] or 0 for r in rows)},
        "corpus_source": src_summary.get("corpus_source"),
        "compressors": {n: src_summary["compressors"].get(n) for n in names},
        "results": summarize(records, names),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(summary["results"], names)
    print(f"\n저장: results/runs/{run_id}/  잘림 {summary['counts']['length']}  빈 답변 {summary['counts']['empty']}")


if __name__ == "__main__":
    sys.exit(main())
