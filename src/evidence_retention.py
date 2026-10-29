"""
근거 보존율: 압축 문맥에 정답 근거 인용문이 얼마나 남았는지 (API 호출 없음)

저장된 압축 문맥(contexts/<qid>.<압축기>.md)과 평가셋의 evidence[].quote 로 계산한다.

    EVAL_DIR=data/evalsets/claude-v1 python src/evidence_retention.py results/runs/<run_id>

인용문 하나의 보존율 = 압축 문맥에 순서대로 남은 인용문 단어 수 / 인용문 단어 수
    단어는 grader.word_tokens 기준 (소문자 영숫자). 압축은 단어를 지우기만 하므로, 남은 단어는 압축 문맥의
    한 구간에 순서대로 모인다. 그래서 인용문 단어 맞춤 +1, 인용문 단어 건너뜀 0, 사이에 낀 문맥 단어 −1 인
    구간 정렬로 센다 (흩어진 흔한 단어가 맞춤으로 잡히지 않게)
    intact = 공백을 하나로 줄인 인용문 전체가 압축 문맥에 그대로 있음
문항의 보존율 = 인용문 보존율의 단어 수 가중 평균
    같은 run 에 none 이 있으면 none 문맥의 보존율로 나눈 상대 보존율(rel)도 낸다. 인용문 표기가 문맥과 조금
    달라 none 에서도 1.0 이 안 나오는 문항을 보정한다

정확도와 묶어 보기 (A-2: 근거가 사라져도 맞히는가)
    보존율 < --low (기본 0.5) 인 trial 을 근거 소실로 보고, 그중 answer_accuracy >= 0.5 인 수를 센다
결과: 압축기별 요약을 출력하고 <run>/evidence_retention.json 에 문항별 값과 함께 쓴다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import load_items
from grader import word_tokens


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def quote_kept(quote: list[str], ctx: list[str]) -> int:
    """quote 단어 중 ctx 의 한 구간에 순서대로 남은 수 (맞춤 +1, quote 건너뜀 0, 낀 ctx 단어 −1 의 최고 점수)."""
    if not quote or not ctx:
        return 0
    # prev[j]: quote[:i] 와 ctx[:j] 에서 j 에서 끝나는 구간의 최고 점수. 0 행이 모두 0 이라 구간 시작은 자유
    prev = [0] * (len(ctx) + 1)
    for q in quote:
        cur = [0] * (len(ctx) + 1)
        for j, c in enumerate(ctx, 1):
            cur[j] = max(prev[j],                                   # quote 단어가 지워짐
                         cur[j - 1] - 1,                            # 인용문과 무관한 ctx 단어가 낌
                         prev[j - 1] + 1 if q == c else 0)          # 맞춤
        prev = cur
    return max(prev)


def item_retention(context: str, quotes: list[str]) -> dict | None:
    """문항 하나의 근거 보존율. 인용문이 없으면 None."""
    ctx = word_tokens(context)
    flat = _norm(context)
    per = []
    for quote in quotes:
        q = word_tokens(quote)
        if not q:
            continue
        kept = quote_kept(q, ctx)
        per.append({"words": len(q), "kept": kept, "retention": round(kept / len(q), 4),
                    "intact": _norm(quote) in flat})
    if not per:
        return None
    words = sum(p["words"] for p in per)
    return {"retention": round(sum(p["kept"] for p in per) / words, 4),
            "intact_all": all(p["intact"] for p in per),
            "quotes": per}


def summarize(rows: list[dict], low: float) -> dict:
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None

    lost = [r for r in rows if r["retention"] < low]
    return {
        "n": len(rows),
        "retention_mean": mean(r["retention"] for r in rows),
        "retention_rel_mean": mean(r.get("retention_rel") for r in rows),
        "intact_all_rate": mean(float(r["intact_all"]) for r in rows),
        "lost": len(lost),
        "lost_correct": sum(1 for r in lost if (r["answer_accuracy"] or 0) >= 0.5),
        "accuracy_kept": mean(r["answer_accuracy"] for r in rows if r["retention"] >= low),
        "accuracy_lost": mean(r["answer_accuracy"] for r in lost),
    }


def main():
    ap = argparse.ArgumentParser(description="기존 run 의 압축 문맥에서 근거 보존율 계산")
    ap.add_argument("run_dir", help="results/runs/<run_id>")
    ap.add_argument("--low", type=float, default=0.5, help="이 값 미만이면 근거 소실로 본다")
    args = ap.parse_args()

    run = Path(args.run_dir)
    trials = [json.loads(l) for l in open(run / "trials.jsonl", encoding="utf-8") if l.strip()]
    items = {it["id"]: it for it in load_items("all", None, None)}

    rows: dict[str, list[dict]] = {}
    for t in trials:
        item = items.get(t["qid"])
        if item is None:
            sys.exit(f"평가셋에 없는 문항입니다: {t['qid']} (EVAL_DIR 확인)")
        ctx_file = run / "contexts" / f"{t['qid']}.{t['compressor'].replace('>', '+')}.md"
        if not ctx_file.exists():
            sys.exit(f"압축 문맥 파일이 없습니다: {ctx_file}")
        quotes = [e["quote"] for e in item.get("evidence") or [] if e.get("quote")]
        r = item_retention(ctx_file.read_text(encoding="utf-8"), quotes)
        if r is None:
            continue
        rows.setdefault(t["compressor"], []).append(
            {"qid": t["qid"], "qtype": t["qtype"], "answer_accuracy": t.get("answer_accuracy"), **r})

    base = {r["qid"]: r["retention"] for r in rows.get("none", [])}
    for rs in rows.values():
        for r in rs:
            b = base.get(r["qid"])
            if b:
                r["retention_rel"] = round(min(1.0, r["retention"] / b), 4)

    out = {"run": run.as_posix(), "low": args.low,
           "results": {c: {**summarize(rs, args.low), "items": rs} for c, rs in rows.items()}}
    (run / "evidence_retention.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    def fmt(x):
        return "-" if x is None else f"{x:.3f}"

    print(f"{'압축기':<16}{'n':>4}{'보존율':>8}{'상대':>8}{'원문유지':>8}  근거 소실(<{args.low}) 중 맞힘   정확도 보존/소실")
    for c, s in out["results"].items():
        print(f"{c:<16}{s['n']:>4}{fmt(s['retention_mean']):>9}{fmt(s['retention_rel_mean']):>9}"
              f"{fmt(s['intact_all_rate']):>9}  {s['lost_correct']:>3} / {s['lost']:<3}"
              f"              {fmt(s['accuracy_kept'])} / {fmt(s['accuracy_lost'])}")


if __name__ == "__main__":
    main()
