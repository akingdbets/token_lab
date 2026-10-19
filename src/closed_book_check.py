"""
문서 없이 풀기(closed-book) 재검사 — 현재 답변 모델 기준

평가셋을 만들 때의 문서 없이 풀기 검사(dataset_builder.py)는 그때 답변 모델(qwen2.5:7b) 기준이다.
답변 모델이 바뀌면 그 모델이 문서 없이 맞히는 문항이 달라지므로 다시 확인한다. 평가셋 파일은 고치지 않는다.

각 문항에 대해 답변 모델(config ANSWER_*)에 문서 없이 질문만 보낸다 (dataset_builder.CLOSED_BOOK_PROMPT 그대로).
    판정 A  grader.closed_book_knows: 평가셋 필터와 같은 기준 (짧은 답은 정답 단어, 긴 답은 핵심 개체 절반 이상)
    판정 B  같은 답변을 key_facts judge(JUDGE_*, per_fact)로 채점한 closed-book 정확도 (0~1).
            답변이 UNKNOWN 이면 judge 없이 0
    UNKNOWN 답변 비율도 따로 센다
    빈 답변(생각 토큰만으로 출력 한도를 다 써서 본문이 없음)은 판정 B 에서 뺀다 (None, empty 로 표시).
    judge 는 채점 프롬프트에 정답이 있어 빈 답변에도 YES 를 줄 수 있다

    EVAL_DIR=data/evalsets/claude-v1 python src/closed_book_check.py --split all
    EVAL_DIR=data/evalsets/claude-v1 python src/closed_book_check.py --split all --resume   # 중단된 곳부터

결과: results/closed_book_luna/closed_book.jsonl (문항별), summary.json (split x type 집계, 생성 조건)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from dataset_builder import CLOSED_BOOK_PROMPT, OUTPUT_RESERVE
from experiment import FACT_JUDGE_MAX_TOKENS, TYPES, _mean, git_head, load_items
from grader import FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_PROMPT_VERSION, closed_book_knows, grade_answer_accuracy
from llm import LLM

UNKNOWN = "UNKNOWN"


def is_unknown(response: str) -> bool:
    return response.strip().strip(".").upper().startswith(UNKNOWN)


def is_empty(row: dict) -> bool:
    """답변 본문이 비었는지. 예전 기록(empty 필드 없음)도 response 로 판단한다."""
    return row.get("empty", not row["response"].strip())


def check_item(item: dict, llm: LLM, judge: LLM | None) -> dict:
    q, a = item["question"], item["answer"]
    res = llm.ask(CLOSED_BOOK_PROMPT.format(q=q))
    resp = res.text.strip()
    unknown = is_unknown(resp)
    # dataset_builder 는 문서에 나오는 핵심 개체만 쓴다 (kept_ents). 평가셋의 key_entities 가 그 결과
    ents = item.get("key_entities") or [a]
    knows, rule = closed_book_knows(resp, a, ents)

    row = {
        "qid": item["id"], "split": item.get("split"), "qtype": item["type"],
        "question": q, "answer": a, "response": resp, "unknown": unknown, "empty": not resp,
        "knows": knows, "rule": rule,
        "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
        "usage_source": res.usage_source, "finish_reason": res.finish_reason, "answer_model": res.model,
        "cb_accuracy": None, "satisfied_facts": None, "total_facts": len(item.get("key_facts") or []),
        "fact_results": [], "judge_failed": [], "judge_calls": 0,
        "judge_prompt_tokens": 0, "judge_completion_tokens": 0,
    }
    if judge is None:
        return row
    if unknown:
        row["cb_accuracy"] = 0.0
        return row
    if not resp:   # 판정 B 에서 뺀다 (judge 가 빈 답변에도 정답을 보고 YES 를 줄 수 있음)
        return row
    g = grade_answer_accuracy(q, a, item["key_facts"], resp, judge, mode="per_fact")
    row.update({
        "cb_accuracy": g.answer_accuracy,          # 못 읽은 fact 가 있으면 None
        "satisfied_facts": g.satisfied_count,
        "fact_results": [{"fact": r.fact, "satisfied": r.satisfied} for r in g.fact_results],
        "judge_failed": g.judge_failed, "judge_calls": g.judge_calls,
        "judge_prompt_tokens": g.judge_prompt_tokens, "judge_completion_tokens": g.judge_completion_tokens,
    })
    return row


def summarize(rows: list[dict]) -> dict:
    """split x type (+ 전체) 별: 판정 A 로 문서 없이 푼 수·비율, 판정 B 평균, UNKNOWN 비율.
    빈 답변은 판정 B 에서 뺀다 (예전 기록에 judge 점수가 있어도 무시)."""
    def cb(r):
        return None if is_empty(r) else r["cb_accuracy"]

    def stats(rs):
        n = len(rs)
        return {
            "n": n,
            "knows": sum(r["knows"] for r in rs),
            "knows_rate": round(sum(r["knows"] for r in rs) / n, 4) if n else None,
            "cb_accuracy": _mean(cb(r) for r in rs),
            "cb_ge_0_5": sum((cb(r) or 0) >= 0.5 for r in rs),
            "unknown_rate": round(sum(r["unknown"] for r in rs) / n, 4) if n else None,
            "empty": sum(is_empty(r) for r in rs),
        }
    out = {"all": stats(rows)}
    for split in sorted({r["split"] for r in rows}):
        rs = [r for r in rows if r["split"] == split]
        out[split] = {"all": stats(rs), **{t: stats([r for r in rs if r["qtype"] == t])
                                           for t in TYPES if any(r["qtype"] == t for r in rs)}}
    out["usage"] = {k: sum(r[k] for r in rows) for k in
                    ("prompt_tokens", "completion_tokens", "judge_prompt_tokens", "judge_completion_tokens")}
    out["usage"]["judge_calls"] = sum(r["judge_calls"] for r in rows)
    out["judge_failed_items"] = sum(bool(r["judge_failed"]) for r in rows)
    out["truncated"] = sum(r["finish_reason"] == "length" for r in rows)
    return out


def subset_report(trials: list[dict], cb_rows: list[dict]) -> dict:
    """실험 run(trials.jsonl)을 '문서 없이 푼 문항'을 뺀 부분집합으로 다시 집계 (API 호출 없음).
    제외 기준 두 가지: 판정 A (knows) / 판정 B >= 0.5. 압축기별 평균 정확도와 none 대비 유지율."""
    cb = {r["qid"]: r for r in cb_rows}
    rules = {
        "all": lambda q: True,
        "exclude_A": lambda q: not cb[q]["knows"],
        "exclude_B_ge_0_5": lambda q: is_empty(cb[q]) or (cb[q]["cb_accuracy"] or 0) < 0.5,
    }
    comps = list(dict.fromkeys(t["compressor"] for t in trials))
    out = {}
    for name, keep in rules.items():
        qids = sorted({t["qid"] for t in trials if t["qid"] in cb and keep(t["qid"])})
        acc = {c: _mean(t["answer_accuracy"] for t in trials if t["compressor"] == c and t["qid"] in qids)
               for c in comps}
        base = acc.get("none")
        out[name] = {
            "n": len(qids),
            "excluded": sorted({t["qid"] for t in trials if t["qid"] in cb} - set(qids)),
            "answer_accuracy": acc,
            "retention_pct": {c: (round(100 * acc[c] / base, 2) if base and acc[c] is not None else None)
                              for c in comps if c != "none"},
        }
    return out


def main():
    ap = argparse.ArgumentParser(description="현재 답변 모델로 문서 없이 풀기(closed-book) 재검사")
    ap.add_argument("--split", default="all", choices=("dev", "test", "all"))
    ap.add_argument("--limit", type=int, help="앞에서부터 N 문항만")
    ap.add_argument("--ids", nargs="*", help="특정 문항만")
    ap.add_argument("--out", default=str(CFG.results_dir / "closed_book_luna"), help="결과 폴더")
    ap.add_argument("--no-judge", action="store_true", help="판정 B(key_facts judge) 생략")
    ap.add_argument("--resume", action="store_true", help="결과 jsonl 에 이미 있는 문항은 건너뛰고 이어 쓴다")
    ap.add_argument("--summarize-only", action="store_true",
                    help="호출 없이 결과 jsonl 로 summary.json 의 results 만 다시 만든다 (생성 조건 등은 유지)")
    ap.add_argument("--subset-run", metavar="TRIALS",
                    help="검사는 하지 않고, 이 trials.jsonl 을 문서 없이 푼 문항을 뺀 부분집합으로 다시 집계")
    args = ap.parse_args()

    out = Path(args.out)
    path = out / "closed_book.jsonl"
    if args.subset_run:
        trials = [json.loads(l) for l in open(args.subset_run, encoding="utf-8") if l.strip()]
        cb_rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        rep = {"run": args.subset_run, **subset_report(trials, cb_rows)}
        (out / "subset_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    if args.summarize_only:
        old = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        old["results"] = summarize([json.loads(l) for l in open(path, encoding="utf-8") if l.strip()])
        old["resummarized"] = datetime.now().isoformat(timespec="seconds")
        (out / "summary.json").write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(old["results"]["all"], ensure_ascii=False))
        return
    out.mkdir(parents=True, exist_ok=True)
    done = set()
    if path.exists():
        if not args.resume:
            sys.exit(f"{path} 가 이미 있습니다. 이어 하려면 --resume, 새로 하려면 파일을 옮기세요")
        done = {json.loads(l)["qid"] for l in open(path, encoding="utf-8") if l.strip()}

    items = [it for it in load_items(args.split, args.limit, args.ids) if it["id"] not in done]
    # dataset_builder 의 문서 없이 풀기와 같은 출력 한도
    llm = LLM(max_tokens=OUTPUT_RESERVE)
    judge = None if args.no_judge else LLM(role="judge", max_tokens=FACT_JUDGE_MAX_TOKENS)
    print(f"답변 {llm.model} ({llm.backend})  judge {'off' if judge is None else judge.model}  "
          f"문항 {len(items)}개 (이미 한 문항 {len(done)}개 건너뜀)  ->  {path}", flush=True)

    with open(path, "a", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            row = check_item(item, llm, judge)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            acc = "-" if row["cb_accuracy"] is None else f"{row['cb_accuracy']:.2f}"
            print(f"[{i}/{len(items)}] {row['qid']} {row['split']:<4} {row['qtype']:<9} "
                  f"{'UNKNOWN' if row['unknown'] else 'answered'}  A={'knows' if row['knows'] else '-'}  B={acc}",
                  flush=True)

    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "eval_dir": CFG.eval_dir.relative_to(CFG.root).as_posix(),
        "prompt": "dataset_builder.CLOSED_BOOK_PROMPT",
        "sampling": {"answer": llm.sampling_info(), "judge": None if judge is None else judge.sampling_info()},
        "fact_judge": {"prompt_version": FACT_JUDGE_PROMPT_VERSION, "prompt_hash": FACT_JUDGE_PROMPT_HASH,
                       "mode": "per_fact"},
        "results": summarize(rows),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    r = summary["results"]["all"]
    print(f"\n전체 {r['n']}문항: 판정 A 문서 없이 정답 {r['knows']} ({r['knows_rate']:.1%}), "
          f"판정 B 평균 {r['cb_accuracy']}, UNKNOWN {r['unknown_rate']:.1%}")


if __name__ == "__main__":
    main()
